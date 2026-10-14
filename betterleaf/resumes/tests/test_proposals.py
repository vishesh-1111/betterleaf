from __future__ import annotations

from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import ResumeEditProposal
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.services import proposals
from betterleaf.resumes.services.schemas import ResumeData


def _resume(db, structured_data: dict | None = None) -> Resume:
    workspace = Workspace.objects.create()
    return Resume.objects.create(
        workspace=workspace,
        title="Test Resume",
        template="jakes",
        main_tex="",
        structured_data=structured_data or {},
    )


def _data() -> ResumeData:
    return ResumeData.model_validate(
        {
            "name": "A",
            "summary": {"text": "hello"},
            "experience": [
                {
                    "company": "Acme",
                    "duration": "2020",
                    "role": "Dev",
                    "bullets": [
                        {"text": "Worked on APIs"},
                        {"text": "Old bullet"},
                    ],
                },
                {
                    "company": "Beta",
                    "duration": "2021",
                    "role": "Lead",
                    "bullets": [{"text": "Lead work"}],
                },
            ],
            "technical_skills": [
                {"key": "Languages", "value": "Python, C"},
                {"key": "Ops", "value": "Linux"},
            ],
        },
    )


def test_diff_detects_replace_add_reorder(db):
    old = _data()
    new_raw = old.model_dump()
    # edit a bullet's text
    new_raw["experience"][0]["bullets"][0]["text"] = "Built REST APIs"
    # append a new bullet
    new_raw["experience"][0]["bullets"].append({"text": "New bullet"})
    # swap the two surviving bullets
    b = new_raw["experience"][0]["bullets"]
    b[0], b[1] = b[1], b[0]
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    by_op: dict[str, list] = {}
    for ch in changes:
        by_op.setdefault(ch["op"], []).append(ch)

    assert len(by_op["replace"]) == 1
    assert len(by_op["add"]) == 1
    assert len(by_op["reorder"]) == 1
    # reorder is a separate, independent change on the bullet list only
    assert by_op["reorder"][0]["path"] == [
        "experience",
        old.model_dump()["experience"][0]["id"],
        "bullets",
    ]


def test_diff_reorder_parent_is_independent_of_children(db):
    old = _data()
    new_raw = old.model_dump()
    new_raw["experience"][0], new_raw["experience"][1] = (
        new_raw["experience"][1],
        new_raw["experience"][0],
    )
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    reorders = [c for c in changes if c["op"] == "reorder"]
    assert len(reorders) == 1
    assert reorders[0]["path"] == ["experience"]
    # no content changes leaked out of the reorder
    assert all(c["op"] in ("reorder",) for c in changes)


def test_apply_all_changes_reproduces_new_data(db):
    old = _data()
    new_raw = old.model_dump()
    new_raw["experience"][0]["bullets"][0]["text"] = "Built REST APIs"
    new_raw["experience"][0]["bullets"].append({"text": "New bullet"})
    b = new_raw["experience"][0]["bullets"]
    b[0], b[1] = b[1], b[0]
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    applied = old.model_dump()
    for ch in changes:
        assert proposals.apply_one(applied, ch) == "accepted"

    assert ResumeData.model_validate(applied).model_dump() == new.model_dump()


def test_accept_applies_selected_and_regenerates_latex(db):
    old = _data()
    resume = _resume(db, old.model_dump())

    new_raw = old.model_dump()
    new_raw["experience"][0]["bullets"][0]["text"] = "Built REST APIs"
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    for ch in changes:
        ch["id"] = proposals.new_id()
        ch["status"] = "pending"
    proposal = ResumeEditProposal.objects.create(
        resume=resume,
        prompt="improve",
        changes=changes,
    )

    accepted_ids = [c["id"] for c in changes if c["op"] == "replace"]
    proposals.accept(proposal, accepted_ids)

    resume.refresh_from_db()
    proposal.refresh_from_db()
    assert (
        resume.structured_data["experience"][0]["bullets"][0]["text"]
        == "Built REST APIs"
    )
    assert "\\section" in resume.main_tex  # LaTeX regenerated
    for ch in proposal.changes:
        if ch["op"] == "replace":
            assert ch["status"] == "accepted"


def test_reject_never_touches_data(db):
    old = _data()
    resume = _resume(db, old.model_dump())

    new_raw = old.model_dump()
    new_raw["experience"][0]["bullets"][0]["text"] = "Built REST APIs"
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    for ch in changes:
        ch["id"] = proposals.new_id()
        ch["status"] = "pending"
    proposal = ResumeEditProposal.objects.create(
        resume=resume,
        prompt="improve",
        changes=changes,
    )

    rejected_ids = [c["id"] for c in changes]
    proposals.reject(proposal, rejected_ids)

    resume.refresh_from_db()
    proposal.refresh_from_db()
    assert (
        resume.structured_data["experience"][0]["bullets"][0]["text"]
        == "Worked on APIs"
    )
    assert all(ch["status"] == "rejected" for ch in proposal.changes)
    assert proposal.status == ResumeEditProposal.Status.APPLIED


def test_stale_replace_is_skipped(db):
    old = _data()
    resume = _resume(db, old.model_dump())

    new_raw = old.model_dump()
    new_raw["summary"]["text"] = "edited"
    new = ResumeData.model_validate(new_raw)

    changes = proposals.diff(old.model_dump(), new.model_dump())
    replace = next(c for c in changes if c["op"] == "replace")
    replace["id"] = proposals.new_id()
    replace["status"] = "pending"
    proposal = ResumeEditProposal.objects.create(
        resume=resume,
        prompt="edit summary",
        changes=[replace],
    )

    # user edits the summary manually, so `before` no longer matches
    resume.structured_data["summary"]["text"] = "manually changed"
    resume.save(update_fields=["structured_data"])

    proposals.accept(proposal, [replace["id"]])

    resume.refresh_from_db()
    proposal.refresh_from_db()
    assert resume.structured_data["summary"]["text"] == "manually changed"
    assert proposal.changes[0]["status"] == "skipped"
