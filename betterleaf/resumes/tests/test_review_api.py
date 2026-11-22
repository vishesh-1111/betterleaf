"""What the Review tab needs: answer targets and finding a job after a reload."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import TailorRequest
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.master_view import answer_targets
from betterleaf.users.tests.factories import UserFactory

Status = TailorRequest.Status


@pytest.fixture
def master_data():
    return ResumeData.model_validate(
        {
            "name": "Jane",
            "experience": [
                {"company": "Acme", "role": "Engineer", "duration": "2020-2022",
                 "bullets": ["Built REST APIs in Python"]},
            ],
            "projects": [{"title": "Leaf", "tech_stack": "Django", "bullets": ["x"]}],
            "achievements": [{"title": "Won a hackathon"}],
            "education": [
                {"institution": "MIT", "degree": "BS", "duration": "2016-2020"},
            ],
            "technical_skills": [{"key": "Tools", "value": "Git"}],
        },
    ).model_dump()


@pytest.fixture
def setup(db, master_data):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)
    master = MasterResume.objects.create(
        workspace=workspace, title="m", structured_data=master_data,
    )
    original = Resume.objects.create(
        workspace=workspace, master_resume=master, title="m", template="jakes",
    )
    client = APIClient()
    client.force_login(user)
    return client, workspace, master, original


def _tailor(workspace, master, **fields):
    return TailorRequest.objects.create(
        workspace=workspace, master_resume=master, job_text="job", **fields,
    )


def test_answer_targets_lists_only_places_a_bullet_can_go(master_data):
    targets = answer_targets(master_data)
    assert [(t["source_type"], t["label"]) for t in targets] == [
        ("experience", "Acme, Engineer (2020-2022)"),
        ("projects", "Leaf | Django"),
        ("achievements", "Won a hackathon"),
    ]
    assert targets[0]["item_id"] == master_data["experience"][0]["id"]


def test_ready_request_includes_answer_targets(setup):
    client, workspace, master, _ = setup
    tailor = _tailor(workspace, master, status=Status.READY, result={"requirements": []})
    res = client.get(f"/api/tailor-requests/{tailor.id}/")
    assert res.status_code == 200
    assert {t["source_type"] for t in res.data["answer_targets"]} == {
        "experience", "projects", "achievements",
    }


def test_analysing_request_has_job_text_but_no_report_fields(setup):
    client, workspace, master, _ = setup
    tailor = _tailor(workspace, master)
    res = client.get(f"/api/tailor-requests/{tailor.id}/")
    assert res.data["job_text"] == "job"
    assert "answer_targets" not in res.data


def test_resume_shows_its_tailor_request_id(setup):
    client, workspace, master, original = setup
    tailored = Resume.objects.create(
        workspace=workspace, master_resume=master, title="t", template="jakes",
    )
    tailor = _tailor(workspace, master, status=Status.READY, resume=tailored)

    assert client.get(f"/api/resumes/{tailored.id}/").data["tailor_request_id"] == str(
        tailor.id,
    )
    assert client.get(f"/api/resumes/{original.id}/").data["tailor_request_id"] is None


def test_workspace_lists_tailor_request_ids_for_resumes(setup):
    client, workspace, master, original = setup
    tailored = Resume.objects.create(
        workspace=workspace, master_resume=master, title="t", template="jakes",
    )
    tailor = _tailor(workspace, master, status=Status.READY, resume=tailored)

    by_id = {r["id"]: r for r in client.get("/api/workspace/").data["resumes"]}
    assert by_id[str(tailored.id)]["tailor_request_id"] == str(tailor.id)
    assert by_id[str(original.id)]["tailor_request_id"] is None


@pytest.mark.parametrize("state", [Status.ANALYSING, Status.DRAFTING])
def test_workspace_reports_running_job(setup, state):
    client, workspace, master, _ = setup
    tailor = _tailor(workspace, master, status=state)
    assert client.get("/api/workspace/").data["active_tailor_request_id"] == str(
        tailor.id,
    )


def test_workspace_ignores_finished_failed_and_stuck_jobs(setup):
    client, workspace, master, _ = setup
    _tailor(workspace, master, status=Status.READY)
    _tailor(workspace, master, status=Status.FAILED)
    stuck = _tailor(workspace, master, status=Status.ANALYSING)
    TailorRequest.objects.filter(pk=stuck.pk).update(
        updated_at=timezone.now() - timedelta(minutes=30),
    )
    assert client.get("/api/workspace/").data["active_tailor_request_id"] is None


def test_workspace_does_not_see_other_workspaces_jobs(setup, master_data):
    client, *_ = setup
    other = Workspace.objects.create(user=UserFactory.create())
    other_master = MasterResume.objects.create(
        workspace=other, title="o", structured_data=master_data,
    )
    _tailor(other, other_master)
    assert client.get("/api/workspace/").data["active_tailor_request_id"] is None
