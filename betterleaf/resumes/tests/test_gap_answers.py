from unittest import mock

import pytest

from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.gap_answers import GapAnswerError
from betterleaf.resumes.services.tailor.gap_answers import draft_proposals
from betterleaf.resumes.services.tailor.gap_answers import validate_answers

LLM = "betterleaf.resumes.services.tailor.gap_answers.post_deepseek_chat"
REQUIREMENTS = [{"id": "req_2", "text": "Kubernetes"}]
GAPS = [{"requirement_id": "req_2", "question": "Used Kubernetes?"}]


@pytest.fixture
def master():
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


def _answers(master, **overrides):
    answer = {
        "requirement_id": "req_2",
        "source_type": "experience",
        "item_id": master["experience"][0]["id"],
        "text": "I used Kubernetes to deploy our Django apps",
    }
    return [{**answer, **overrides}]


def _proposal(master, **overrides):
    proposal = {
        "requirement_id": "req_2",
        "change": "add_bullet",
        "bullet": "Deployed Django applications on Kubernetes",
        "skill": "Kubernetes",
        "skill_group_id": master["technical_skills"][0]["id"],
    }
    return {"proposals": [{**proposal, **overrides}]}


def test_valid_answers_pass(master):
    validate_answers(_answers(master), master, GAPS)


@pytest.mark.parametrize(
    "overrides",
    [
        {"requirement_id": "req_9"},
        {"source_type": "education"},
        {"item_id": "nope"},
        {"text": "  "},
    ],
)
def test_bad_answers_rejected(master, overrides):
    with pytest.raises(GapAnswerError):
        validate_answers(_answers(master, **overrides), master, GAPS)


def test_duplicate_answer_rejected(master):
    answers = _answers(master) * 2
    with pytest.raises(GapAnswerError):
        validate_answers(answers, master, GAPS)


def test_drafts_proposal_with_target_from_the_answer(master):
    with mock.patch(LLM, return_value=_proposal(master)):
        result = draft_proposals("JD", REQUIREMENTS, _answers(master), master)

    assert len(result) == 1
    assert result[0]["item_id"] == master["experience"][0]["id"]
    assert result[0]["source_type"] == "experience"
    assert result[0]["requirement_text"] == "Kubernetes"
    assert result[0]["bullet"] == "Deployed Django applications on Kubernetes"
    assert result[0]["id"]


def test_no_change_clears_bullet_and_skill(master):
    raw = _proposal(master, change="no_change", reason="Too thin")
    with mock.patch(LLM, return_value=raw):
        result = draft_proposals("JD", REQUIREMENTS, _answers(master), master)
    assert result[0]["bullet"] == ""
    assert result[0]["skill"] == ""
    assert result[0]["reason"] == "Too thin"


def test_retries_once_then_succeeds(master):
    bad = _proposal(master, skill_group_id="nope")
    with mock.patch(LLM, side_effect=[bad, _proposal(master)]) as llm:
        result = draft_proposals("JD", REQUIREMENTS, _answers(master), master)
    assert llm.call_count == 2
    assert "unknown skill_group_id" in llm.call_args_list[1].args[1]
    assert result[0]["bullet"]


def test_gives_up_after_second_bad_answer(master):
    bad = {"proposals": []}
    with mock.patch(LLM, return_value=bad) as llm, pytest.raises(GapAnswerError):
        draft_proposals("JD", REQUIREMENTS, _answers(master), master)
    assert llm.call_count == 2
