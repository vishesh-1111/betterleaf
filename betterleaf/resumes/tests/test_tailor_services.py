from unittest import mock

import pytest

from betterleaf.resumes.services.latex import render_resume
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.analyse import TailoringError
from betterleaf.resumes.services.tailor.analyse import analyse_job_fit
from betterleaf.resumes.services.tailor.assemble import build_tailored_resume_data
from betterleaf.resumes.services.tailor.master_view import add_missing_ids
from betterleaf.resumes.services.tailor.master_view import render_master_for_prompt
from betterleaf.resumes.services.tailor.schemas import Requirement
from betterleaf.resumes.services.tailor.scores import score_requirements

ANALYSE = "betterleaf.resumes.services.tailor.analyse.post_deepseek_chat"


@pytest.fixture
def master():
    return ResumeData.model_validate(
        {
            "name": "Jane",
            "experience": [
                {
                    "company": "Acme", "role": "Engineer", "duration": "2020-2022",
                    "bullets": ["Built REST APIs in Python", "Ran standups"],
                },
            ],
            "technical_skills": [{"key": "Languages", "value": "Python, Go"}],
            "education": [{"institution": "MIT", "degree": "BS", "duration": "2016-2020"}],
        },
    ).model_dump()


def _answer(master, **overrides):
    exp = master["experience"][0]
    answer = {
        "requirements": [
            {
                "id": "req_1", "text": "Python", "importance": "must_have",
                "priority": 1, "status": "met",
                "evidence": [{"source_id": exp["bullets"][0]["id"], "quote": "REST APIs in Python"}],
            },
            {"id": "req_2", "text": "Kubernetes", "importance": "must_have",
             "priority": 2, "status": "not_met"},
            {"id": "req_3", "text": "Go", "importance": "nice_to_have",
             "priority": 3, "status": "partial",
             "evidence": [{"source_id": master["technical_skills"][0]["id"], "quote": "Go"}]},
        ],
        "gap_questions": [
            {"requirement_id": "req_2", "question": "Used Kubernetes?"},
            {"requirement_id": "req_3", "question": "Go?"},
        ],
        "selection": {
            "experience": [{"id": exp["id"], "bullet_ids": [exp["bullets"][0]["id"]]}],
            "education": [master["education"][0]["id"]],
            "technical_skills": [
                {"id": master["technical_skills"][0]["id"], "skills": ["Python"]},
            ],
        },
    }
    answer.update(overrides)
    return answer


def test_add_missing_ids_upgrades_old_master_and_keeps_ids():
    old = {"name": "J", "experience": [
        {"company": "A", "role": "R", "duration": "D", "bullets": ["x"]}]}
    upgraded = add_missing_ids(old)
    assert upgraded["experience"][0]["bullets"][0]["text"] == "x"
    assert add_missing_ids(upgraded) == upgraded


def test_prompt_view_lists_ids(master):
    text = render_master_for_prompt(master)
    assert f"[exp:{master['experience'][0]['id']}] Acme, Engineer" in text
    assert "Built REST APIs in Python" in text


def test_analyse_tidies_gap_questions_and_scores(master):
    with mock.patch(ANALYSE, return_value=_answer(master)):
        analysis = analyse_job_fit("job", master)
    assert [q.requirement_id for q in analysis.gap_questions] == ["req_2"]
    scores = score_requirements(analysis.requirements)
    assert scores == {
        "must_have": {"earned": 1.0, "total": 2},
        "nice_to_have": {"earned": 0.5, "total": 1},
    }


def test_analyse_retries_once_then_gives_up(master):
    bad = _answer(master)
    bad["requirements"][0]["evidence"][0]["source_id"] = "nope"
    with mock.patch(ANALYSE, return_value=bad) as post:
        with pytest.raises(TailoringError):
            analyse_job_fit("job", master)
    assert post.call_count == 2
    assert "unknown evidence id" in post.call_args.args[1]


def test_analyse_repairs_bad_quote_without_retry(master):
    bad = _answer(master)
    bad["requirements"][0]["evidence"][0]["quote"] = "made up"
    with mock.patch(ANALYSE, return_value=bad) as post:
        analysis = analyse_job_fit("job", master)
    assert post.call_count == 1
    assert analysis.requirements[0].evidence[0].quote == "Built REST APIs in Python"


def test_analyse_recovers_on_second_attempt(master):
    bad = _answer(master)
    bad["selection"]["experience"][0]["bullet_ids"] = ["nope"]
    with mock.patch(ANALYSE, side_effect=[bad, _answer(master)]) as post:
        analyse_job_fit("job", master)
    assert post.call_count == 2


def test_tailored_resume_uses_master_words_only(master):
    with mock.patch(ANALYSE, return_value=_answer(master)):
        analysis = analyse_job_fit("job", master)
    data = build_tailored_resume_data(master, analysis.selection)
    assert [b["text"] for b in data["experience"][0]["bullets"]] == [
        "Built REST APIs in Python",
    ]
    assert data["technical_skills"][0]["value"] == "Python"
    assert "Built REST APIs in Python" in render_resume(data)


def test_analyse_tells_the_llm_which_gaps_are_handled(master):
    handled = [{"requirement": "Kubernetes", "outcome": "skipped"}]
    with mock.patch(ANALYSE, return_value=_answer(master)) as post:
        analyse_job_fit("job", master, handled_gaps=handled)
    assert "ALREADY HANDLED\n- Kubernetes (skipped)" in post.call_args.args[1]

    with mock.patch(ANALYSE, return_value=_answer(master)) as post:
        analyse_job_fit("job", master)
    assert "ALREADY HANDLED" not in post.call_args.args[1]


def test_analyse_cuts_each_skill_group_to_ten(master):
    group = master["technical_skills"][0]
    names = [f"Go{n}" for n in range(15)]
    group["value"] = ", ".join(names)
    answer = _answer(master)
    answer["selection"]["technical_skills"] = [{"id": group["id"], "skills": names}]
    with mock.patch(ANALYSE, return_value=answer):
        analysis = analyse_job_fit("job", master)
    assert analysis.selection.technical_skills[0].skills == names[:10]
