"""Gap answers → proposals → confirm → follow-up tailor request."""

from unittest import mock

import pytest
from rest_framework.test import APIClient

from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import TailorRequest
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.gap_answers import GapAnswerError
from betterleaf.resumes.services.tailor.schemas import TailoringAnalysis
from betterleaf.resumes.tasks import analyse_job
from betterleaf.resumes.tasks import draft_gap_proposals
from betterleaf.users.tests.factories import UserFactory

DRAFT = "betterleaf.resumes.views.draft_gap_proposals"
ANALYSE = "betterleaf.resumes.views.analyse_job"


@pytest.fixture
def master_data():
    return ResumeData.model_validate(
        {
            "name": "Jane",
            "experience": [
                {"company": "Acme", "role": "Engineer", "duration": "2020-2022",
                 "bullets": ["Built REST APIs in Python"]},
            ],
            "technical_skills": [{"key": "Tools", "value": "Git, Linux"}],
        },
    ).model_dump()


@pytest.fixture
def setup(db, master_data):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)
    master = MasterResume.objects.create(
        workspace=workspace, title="m", structured_data=master_data,
    )
    client = APIClient()
    client.force_login(user)
    tailor = TailorRequest.objects.create(
        workspace=workspace,
        master_resume=master,
        job_text="We need Kubernetes and Terraform",
        status=TailorRequest.Status.READY,
        counted=True,
        result={
            "requirements": [
                {"id": "req_1", "text": "Kubernetes", "importance": "must_have",
                 "priority": 1, "status": "not_met", "evidence": [], "rationale": ""},
                {"id": "req_2", "text": "Terraform", "importance": "must_have",
                 "priority": 2, "status": "not_met", "evidence": [], "rationale": ""},
            ],
            "gap_questions": [
                {"requirement_id": "req_1", "question": "Kubernetes?"},
                {"requirement_id": "req_2", "question": "Terraform?"},
            ],
        },
    )
    return client, tailor, master


def _url(tailor, action):
    return f"/api/tailor-requests/{tailor.id}/{action}/"


def _answer(master, **overrides):
    answer = {
        "requirement_id": "req_1",
        "source_type": "experience",
        "item_id": master.structured_data["experience"][0]["id"],
        "text": "I deployed our Django apps on Kubernetes",
    }
    return {**answer, **overrides}


def _proposal(master, **overrides):
    proposal = {
        "id": "p1",
        "requirement_id": "req_1",
        "requirement_text": "Kubernetes",
        "source_type": "experience",
        "item_id": master.structured_data["experience"][0]["id"],
        "change": "add_bullet",
        "bullet": "Deployed Django applications on Kubernetes",
        "skill": "Kubernetes",
        "skill_group_id": master.structured_data["technical_skills"][0]["id"],
        "reason": "",
    }
    return {**proposal, **overrides}


# --- answers -----------------------------------------------------------------


def test_answers_saved_and_drafting_queued(setup, django_capture_on_commit_callbacks):
    client, tailor, master = setup
    with mock.patch(DRAFT) as task, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(
            _url(tailor, "answers"), {"answers": [_answer(master)]}, format="json",
        )

    assert resp.status_code == 202
    assert resp.json() == {"id": str(tailor.id), "status": "drafting"}
    task.delay.assert_called_once_with(str(tailor.id))
    tailor.refresh_from_db()
    assert tailor.status == "drafting"
    assert tailor.answers[0]["text"] == "I deployed our Django apps on Kubernetes"


@pytest.mark.parametrize(
    "overrides",
    [{"item_id": "nope"}, {"requirement_id": "req_9"}, {"source_type": "education"}],
)
def test_answers_rejects_bad_targets(setup, overrides):
    client, tailor, master = setup
    resp = client.post(
        _url(tailor, "answers"), {"answers": [_answer(master, **overrides)]}, format="json",
    )
    assert resp.status_code == 400
    tailor.refresh_from_db()
    assert tailor.status == "ready"


def test_answers_rejects_empty_list(setup):
    client, tailor, _ = setup
    resp = client.post(_url(tailor, "answers"), {"answers": []}, format="json")
    assert resp.status_code == 400


def test_answers_needs_ready_request(setup):
    client, tailor, master = setup
    tailor.status = "analysing"
    tailor.save()
    resp = client.post(
        _url(tailor, "answers"), {"answers": [_answer(master)]}, format="json",
    )
    assert resp.status_code == 409


def test_other_workspace_cannot_answer(setup):
    _, tailor, master = setup
    stranger = UserFactory.create()
    Workspace.objects.create(user=stranger)
    other = APIClient()
    other.force_login(stranger)
    resp = other.post(
        _url(tailor, "answers"), {"answers": [_answer(master)]}, format="json",
    )
    assert resp.status_code == 404


def test_poll_shows_proposals_while_ready(setup):
    client, tailor, master = setup
    tailor.proposals = [_proposal(master)]
    tailor.save()
    body = client.get(f"/api/tailor-requests/{tailor.id}/").json()
    assert body["kind"] == "initial"
    assert body["parent_id"] is None
    assert body["proposals"][0]["id"] == "p1"
    assert len(body["gap_questions"]) == 2


# --- confirm -----------------------------------------------------------------


def test_confirm_updates_master_and_starts_followup(
    setup, django_capture_on_commit_callbacks,
):
    client, tailor, master = setup
    tailor.answers = [_answer(master)]  # req_2 was skipped
    tailor.proposals = [_proposal(master)]
    tailor.save()
    group = master.structured_data["technical_skills"][0]["id"]
    accepted = {
        "id": "p1",
        "bullet": "Deployed Django apps on Kubernetes at Acme",  # user edited it
        "skill": "Kubernetes",
        "skill_group_id": group,
    }

    with mock.patch(ANALYSE) as task, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(_url(tailor, "confirm"), {"accepted": [accepted]}, format="json")

    assert resp.status_code == 202
    child = TailorRequest.objects.get(pk=resp.json()["id"])
    task.delay.assert_called_once_with(str(child.id))
    assert child.parent_id == tailor.id
    assert child.kind == "gap_followup"
    assert child.job_text == tailor.job_text
    assert child.status == "analysing"
    assert child.handled_gaps == [
        {"requirement": "Kubernetes", "outcome": "answered"},
        {"requirement": "Terraform", "outcome": "skipped"},
    ]

    master.refresh_from_db()
    experience = master.structured_data["experience"][0]
    assert [b["text"] for b in experience["bullets"]] == [
        "Built REST APIs in Python",
        "Deployed Django apps on Kubernetes at Acme",
    ]
    assert master.structured_data["technical_skills"][0]["value"] == "Git, Linux, Kubernetes"

    tailor.refresh_from_db()
    assert tailor.status == "ready"  # the old request is untouched


def test_confirm_with_nothing_accepted_changes_nothing(setup):
    client, tailor, master = setup
    tailor.proposals = [_proposal(master)]
    tailor.save()
    resp = client.post(_url(tailor, "confirm"), {"accepted": []}, format="json")
    assert resp.status_code == 200
    assert TailorRequest.objects.count() == 1
    master.refresh_from_db()
    assert len(master.structured_data["experience"][0]["bullets"]) == 1


def test_confirm_ignores_target_sent_by_client(setup):
    client, tailor, master = setup
    tailor.proposals = [_proposal(master)]
    tailor.save()
    accepted = {"id": "p1", "bullet": "x", "item_id": "elsewhere", "source_type": "projects"}
    resp = client.post(_url(tailor, "confirm"), {"accepted": [accepted]}, format="json")
    assert resp.status_code == 202
    master.refresh_from_db()
    assert master.structured_data["experience"][0]["bullets"][-1]["text"] == "x"


def test_confirm_unknown_or_no_change_proposal_rejected(setup):
    client, tailor, master = setup
    tailor.proposals = [_proposal(master, id="p2", change="no_change", bullet="")]
    tailor.save()
    for proposal_id in ("nope", "p2"):
        resp = client.post(
            _url(tailor, "confirm"),
            {"accepted": [{"id": proposal_id, "bullet": "x"}]},
            format="json",
        )
        assert resp.status_code == 400
    assert TailorRequest.objects.count() == 1


def test_confirm_bad_skill_group_changes_nothing(setup):
    client, tailor, master = setup
    tailor.proposals = [_proposal(master)]
    tailor.save()
    accepted = {"id": "p1", "bullet": "ok", "skill": "Kubernetes", "skill_group_id": "nope"}
    resp = client.post(_url(tailor, "confirm"), {"accepted": [accepted]}, format="json")
    assert resp.status_code == 400
    master.refresh_from_db()
    assert len(master.structured_data["experience"][0]["bullets"]) == 1
    assert TailorRequest.objects.count() == 1


# --- tasks -------------------------------------------------------------------


def test_draft_task_saves_proposals_and_returns_to_ready(setup):
    _, tailor, master = setup
    tailor.status = "drafting"
    tailor.answers = [_answer(master)]
    tailor.save()
    drafted = [_proposal(master)]
    with mock.patch("betterleaf.resumes.tasks.draft_proposals", return_value=drafted):
        draft_gap_proposals.apply(args=[str(tailor.id)])
    tailor.refresh_from_db()
    assert tailor.status == "ready"
    assert tailor.proposals == drafted
    assert tailor.error == ""


def test_draft_task_failure_returns_to_ready_with_error(setup):
    _, tailor, master = setup
    tailor.status = "drafting"
    tailor.answers = [_answer(master)]
    tailor.save()
    with mock.patch(
        "betterleaf.resumes.tasks.draft_proposals", side_effect=GapAnswerError("too thin"),
    ):
        draft_gap_proposals.apply(args=[str(tailor.id)])
    tailor.refresh_from_db()
    assert tailor.status == "ready"
    assert tailor.proposals == []
    assert tailor.error == "too thin"


def test_followup_analysis_gets_handled_gaps_and_is_not_counted(setup):
    _, parent, master = setup
    handled = [{"requirement": "Kubernetes", "outcome": "answered"}]
    child = TailorRequest.objects.create(
        workspace=parent.workspace,
        master_resume=master,
        job_text=parent.job_text,
        parent=parent,
        kind=TailorRequest.Kind.GAP_FOLLOWUP,
        handled_gaps=handled,
    )
    analysis = TailoringAnalysis.model_validate(
        {"requirements": [{"id": "req_1", "text": "Kubernetes", "status": "not_met"}]},
    )
    with mock.patch(
        "betterleaf.resumes.tasks.analyse_job_fit", return_value=analysis,
    ) as fit:
        analyse_job.apply(args=[str(child.id)])

    assert fit.call_args.kwargs["handled_gaps"] == handled
    child.refresh_from_db()
    assert child.status == "ready"
    assert child.counted is False
    assert child.resume_id is not None


def test_initial_analysis_is_counted(setup):
    _, _, master = setup
    request = TailorRequest.objects.create(
        workspace=master.workspace, master_resume=master, job_text="job",
    )
    analysis = TailoringAnalysis.model_validate(
        {"requirements": [{"id": "req_1", "text": "Python", "status": "not_met"}]},
    )
    with mock.patch("betterleaf.resumes.tasks.analyse_job_fit", return_value=analysis):
        analyse_job.apply(args=[str(request.id)])
    request.refresh_from_db()
    assert request.counted is True
