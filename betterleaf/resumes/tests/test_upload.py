from __future__ import annotations

from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest
from rest_framework.test import APIClient

from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.services.parser import ResumeParseError
from betterleaf.resumes.services.schemas import ResumeData


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    # Minimal valid PDF so pymupdf can open it; contents are irrelevant because
    # pdf_to_text is patched in tests that exercise the full pipeline.
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Vishesh Kumar Gautam")
    return doc.tobytes()


def test_user_status_guest_no_workspace(db):
    client = APIClient()
    resp = client.get("/api/user-status/")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "has_workspace": False}


def test_user_status_guest_with_workspace(db):
    client = APIClient()
    client.get("/api/workspace/").json()
    resp = client.get("/api/user-status/")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False, "has_workspace": True}


def test_upload_pdf_creates_workspace_resume_and_cookie(db, sample_pdf_bytes):
    client = APIClient()

    data = ResumeData.model_validate(
        {
            "name": "Vishesh Kumar Gautam",
            "experience": [
                {
                    "company": "Senda",
                    "duration": "2025",
                    "role": "Engineer",
                    "bullets": [{"text": "did things"}],
                },
            ],
        },
    )

    with (
        mock.patch(
            "betterleaf.resumes.views.pdf_to_text", return_value="markdown",
        ),
        mock.patch(
            "betterleaf.resumes.views.extract_resume", return_value=data,
        ),
    ):
        resp = client.post(
            "/api/upload-pdf/",
            {
                "file": SimpleUploadedFile(
                    "resume.pdf", sample_pdf_bytes,
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "resume" in body
    assert body["resume"]["title"] == "resume"
    assert body["resume"]["main_tex"].startswith("%")

    # Workspace + resume created and cookie set.
    assert Workspace.objects.count() == 1
    assert Resume.objects.count() == 1
    assert "bl_session" in resp.cookies


def test_upload_pdf_missing_file(db):
    client = APIClient()
    resp = client.post("/api/upload-pdf/", {}, format="multipart")
    assert resp.status_code == 400
    assert "file" in resp.json()["detail"]


def test_upload_pdf_parse_error(db, sample_pdf_bytes):
    client = APIClient()
    with (
        mock.patch(
            "betterleaf.resumes.views.pdf_to_text", return_value="some markdown",
        ),
        mock.patch(
            "betterleaf.resumes.views.extract_resume",
            side_effect=ResumeParseError("bad resume"),
        ),
    ):
        resp = client.post(
            "/api/upload-pdf/",
            {
                "file": SimpleUploadedFile(
                    "resume.pdf", sample_pdf_bytes,
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
    assert resp.status_code == 422
    # A parse failure must not leave an orphaned workspace behind.
    assert Workspace.objects.count() == 0


def test_upload_pdf_existing_workspace_returns_200(db, sample_pdf_bytes):
    client = APIClient()
    # Establish workspace first via the workspace endpoint.
    client.get("/api/workspace/").json()

    data = ResumeData.model_validate({"name": "Vishesh Kumar Gautam"})
    with (
        mock.patch(
            "betterleaf.resumes.views.pdf_to_text", return_value="md",
        ),
        mock.patch(
            "betterleaf.resumes.views.extract_resume", return_value=data,
        ),
    ):
        resp = client.post(
            "/api/upload-pdf/",
            {
                "file": SimpleUploadedFile(
                    "resume.pdf", sample_pdf_bytes,
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
    assert resp.status_code == 200
    assert resp.json()["created"] is False
    assert Workspace.objects.count() == 1
