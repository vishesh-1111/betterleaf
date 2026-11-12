from __future__ import annotations

from unittest import mock

import pytest
from django.db import IntegrityError
from django.db import transaction
from rest_framework.test import APIClient

from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.users.tests.factories import UserFactory

URL = "/api/upload-pdf/task-123/status/"


def _async_result(state: str, result=None, kwargs=None):
    return mock.Mock(state=state, result=result, kwargs=kwargs)


@pytest.fixture
def async_result():
    with mock.patch("betterleaf.resumes.views.AsyncResult") as cls:
        yield cls


@pytest.fixture
def client_and_workspace(db):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)
    client = APIClient()
    client.force_login(user)
    return client, workspace


def test_requires_workspace(db):
    assert APIClient().get(URL).status_code == 403


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("PENDING", "queued"),
        ("RECEIVED", "queued"),
        ("STARTED", "processing"),
        ("RETRY", "processing"),
    ],
)
def test_in_flight_states(client_and_workspace, async_result, state, expected):
    client, _ = client_and_workspace
    async_result.return_value = _async_result(state)

    resp = client.get(URL)

    assert resp.status_code == 200
    assert resp.json() == {"task_id": "task-123", "status": expected}


def test_success_returns_resume_ids(client_and_workspace, async_result):
    client, workspace = client_and_workspace
    master = MasterResume.objects.create(workspace=workspace, title="cv")
    resume = Resume.objects.create(
        workspace=workspace, master_resume=master, title="cv", template="jakes",
    )
    async_result.return_value = _async_result(
        "SUCCESS", result=str(master.id), kwargs={"workspace_id": str(workspace.id)},
    )

    resp = client.get(URL)

    assert resp.status_code == 200
    assert resp.json() == {
        "task_id": "task-123",
        "status": "succeeded",
        "master_resume_id": str(master.id),
        "resume_ids": [str(resume.id)],
    }


def test_failure_hides_exception_details(client_and_workspace, async_result):
    client, _ = client_and_workspace
    async_result.return_value = _async_result(
        "FAILURE", result=NotImplementedError("secret internals"),
    )

    resp = client.get(URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "secret" not in str(body)


def test_other_workspaces_task_is_404(client_and_workspace, async_result):
    client, _ = client_and_workspace
    other = Workspace.objects.create()
    async_result.return_value = _async_result(
        "STARTED", kwargs={"workspace_id": str(other.id)},
    )

    assert client.get(URL).status_code == 404


def test_success_without_own_master_is_404(client_and_workspace, async_result):
    client, _ = client_and_workspace
    other = Workspace.objects.create()
    master = MasterResume.objects.create(workspace=other, title="theirs")
    async_result.return_value = _async_result("SUCCESS", result=str(master.id))

    assert client.get(URL).status_code == 404


def test_workspace_can_have_only_one_master_resume(db):
    workspace = Workspace.objects.create()
    MasterResume.objects.create(workspace=workspace, title="first")

    with pytest.raises(IntegrityError), transaction.atomic():
        MasterResume.objects.create(workspace=workspace, title="second")
