from __future__ import annotations

from datetime import timedelta
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.serializers import MAX_PDF_UPLOAD_BYTES
from betterleaf.users.tests.factories import UserFactory

PDF_BYTES = b"%PDF-1.4\n%minimal\n"


@pytest.fixture(autouse=True)
def queued_task():
    """Never hit Celery/the broker; expose the mocked `.delay`."""
    with mock.patch(
        "betterleaf.resumes.views.parse_and_create_master.delay",
    ) as delay:
        delay.return_value = mock.Mock(id="task-123")
        yield delay


def _pdf(name: str = "resume.pdf", content: bytes = PDF_BYTES) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def _upload(client: APIClient, file: SimpleUploadedFile | None = None):
    data = {} if file is None else {"file": file}
    return client.post("/api/upload-pdf/", data, format="multipart")


# ---- guest upload ----------------------------------------------------------


def test_guest_upload_creates_workspace_cookie_and_queues_task(db, queued_task):
    client = APIClient()

    resp = _upload(client, _pdf())

    assert resp.status_code == 201
    assert resp.json() == {"task_id": "task-123", "status": "queued", "created": True}
    workspace = Workspace.objects.get()
    assert workspace.user_id is None
    assert workspace.expires_at is not None
    assert "bl_session" in resp.cookies
    assert resp.cookies["bl_session"]["httponly"]
    queued_task.assert_called_once()
    kwargs = queued_task.call_args.kwargs
    assert kwargs["workspace_id"] == str(workspace.id)
    assert kwargs["filename"] == "resume.pdf"


def test_guest_second_upload_reuses_workspace(db, queued_task):
    client = APIClient()
    _upload(client, _pdf())

    resp = _upload(client, _pdf("again.pdf"))

    assert resp.status_code == 200
    assert resp.json()["created"] is False
    assert "bl_session" not in resp.cookies
    assert Workspace.objects.count() == 1
    assert queued_task.call_count == 2


def test_guest_upload_with_expired_cookie_creates_new_workspace(db):
    client = APIClient()
    _upload(client, _pdf())
    Workspace.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    resp = _upload(client, _pdf())

    assert resp.status_code == 201
    assert Workspace.objects.count() == 2


# ---- logged-in upload ------------------------------------------------------


def test_authenticated_upload_uses_users_workspace_without_cookie(db, queued_task):
    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    resp = _upload(client, _pdf())

    assert resp.status_code == 200
    assert resp.json()["created"] is False
    assert "bl_session" not in resp.cookies
    workspace = Workspace.objects.get(user=user)
    assert queued_task.call_args.kwargs["workspace_id"] == str(workspace.id)


def test_authenticated_upload_reuses_existing_workspace(db):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)
    client = APIClient()
    client.force_login(user)

    _upload(client, _pdf())

    assert Workspace.objects.get(user=user) == workspace
    assert Workspace.objects.count() == 1


# ---- validation (identical for both) --------------------------------------


@pytest.mark.parametrize(
    "file",
    [
        None,
        SimpleUploadedFile("notes.txt", PDF_BYTES, content_type="text/plain"),
        SimpleUploadedFile("fake.pdf", b"not really a pdf", content_type="application/pdf"),
        SimpleUploadedFile(
            "huge.pdf",
            PDF_BYTES + b"0" * MAX_PDF_UPLOAD_BYTES,
            content_type="application/pdf",
        ),
    ],
    ids=["missing", "wrong-extension", "bad-magic", "too-large"],
)
def test_invalid_upload_is_rejected_without_side_effects(db, queued_task, file):
    client = APIClient()

    resp = _upload(client, file)

    assert resp.status_code == 400
    assert "file" in resp.json()
    assert Workspace.objects.count() == 0
    assert "bl_session" not in resp.cookies
    queued_task.assert_not_called()


# ---- user-status -----------------------------------------------------------


def test_user_status_guest_no_workspace(db):
    resp = APIClient().get("/api/user-status/")

    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "has_workspace": False}
    assert Workspace.objects.count() == 0


def test_user_status_guest_with_workspace(db):
    client = APIClient()
    _upload(client, _pdf())

    resp = client.get("/api/user-status/")

    assert resp.json() == {"authenticated": False, "has_workspace": True}


def test_user_status_authenticated(db):
    client = APIClient()
    client.force_login(UserFactory.create())

    resp = client.get("/api/user-status/")

    assert resp.json() == {"authenticated": True, "has_workspace": True}


# ---- GET /workspace/ -------------------------------------------------------


def test_workspace_without_identity_is_forbidden_and_creates_nothing(db):
    resp = APIClient().get("/api/workspace/")

    assert resp.status_code == 403
    assert "bl_session" not in resp.cookies
    assert Workspace.objects.count() == 0


def test_workspace_for_guest_lists_resumes(db):
    client = APIClient()
    _upload(client, _pdf())
    workspace = Workspace.objects.get()
    Resume.objects.create(workspace=workspace, title="Mine", template="jakes")

    resp = client.get("/api/workspace/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_id"] == str(workspace.id)
    assert body["anonymous"] is True
    assert [r["title"] for r in body["resumes"]] == ["Mine"]
    assert "csrftoken" in resp.cookies


def test_workspace_for_authenticated_user(db):
    user = UserFactory.create()
    client = APIClient()
    client.force_login(user)

    resp = client.get("/api/workspace/")

    assert resp.status_code == 200
    assert resp.json()["anonymous"] is False
    assert resp.json()["workspace_id"] == str(Workspace.objects.get(user=user).id)
