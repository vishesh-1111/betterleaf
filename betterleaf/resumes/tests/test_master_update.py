import pytest

from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.master_update import MasterUpdateError
from betterleaf.resumes.services.tailor.master_update import apply_proposals


@pytest.fixture
def master():
    return ResumeData.model_validate(
        {
            "name": "Jane",
            "experience": [
                {"company": "Acme", "role": "Engineer", "duration": "2020-2022",
                 "bullets": ["Built REST APIs in Python"]},
            ],
            "projects": [{"title": "Inventory", "bullets": []}],
            "technical_skills": [{"key": "Tools", "value": "Git, Linux"}],
        },
    ).model_dump()


def _entry(master, **overrides):
    entry = {
        "source_type": "experience",
        "item_id": master["experience"][0]["id"],
        "bullet": "Deployed Django apps on Kubernetes",
    }
    return {**entry, **overrides}


def test_adds_bullet_with_new_id_and_leaves_input_alone(master):
    updated = apply_proposals(master, [_entry(master)])

    bullets = updated["experience"][0]["bullets"]
    assert [b["text"] for b in bullets] == [
        "Built REST APIs in Python",
        "Deployed Django apps on Kubernetes",
    ]
    assert bullets[1]["id"]
    assert len(master["experience"][0]["bullets"]) == 1


def test_adds_bullet_to_project_with_no_bullets(master):
    entry = _entry(master, source_type="projects", item_id=master["projects"][0]["id"])
    updated = apply_proposals(master, [entry])
    assert len(updated["projects"][0]["bullets"]) == 1


def test_adds_skill_once_ignoring_case(master):
    group = master["technical_skills"][0]["id"]
    entry = _entry(master, skill="Kubernetes", skill_group_id=group)
    updated = apply_proposals(master, [entry, entry])
    assert updated["technical_skills"][0]["value"] == "Git, Linux, Kubernetes"

    again = apply_proposals(updated, [_entry(master, skill="git", skill_group_id=group)])
    assert again["technical_skills"][0]["value"] == "Git, Linux, Kubernetes"


@pytest.mark.parametrize(
    "overrides",
    [
        {"item_id": "nope"},
        {"source_type": "education"},
        {"bullet": "   "},
        {"skill": "Kubernetes", "skill_group_id": "nope"},
    ],
)
def test_bad_entry_raises_and_applies_nothing(master, overrides):
    good = _entry(master)
    with pytest.raises(MasterUpdateError):
        apply_proposals(master, [good, _entry(master, **overrides)])
    assert len(master["experience"][0]["bullets"]) == 1
