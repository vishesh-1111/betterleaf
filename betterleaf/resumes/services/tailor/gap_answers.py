"""Turn the user's gap answers into proposed master-resume bullets."""

import logging
import uuid

from pydantic import ValidationError

from betterleaf.resumes.services.llm import load_prompt
from betterleaf.resumes.services.llm import post_deepseek_chat
from betterleaf.resumes.services.tailor.master_update import BULLET_SECTIONS
from betterleaf.resumes.services.tailor.master_view import index_master
from betterleaf.resumes.services.tailor.master_view import render_item_for_prompt
from betterleaf.resumes.services.tailor.master_view import render_skill_groups_for_prompt
from betterleaf.resumes.services.tailor.schemas import GapProposals

logger = logging.getLogger(__name__)

_MAX_TOKENS = 2000
_MAX_ATTEMPTS = 2  # first try plus one retry with the errors fed back


class GapAnswerError(Exception):
    """The answers are invalid, or the LLM could not draft usable proposals."""


def validate_answers(
    answers: list[dict], master_data: dict, gap_questions: list[dict],
) -> None:
    """Check every answer points at a real gap and a real master item."""
    asked = {q["requirement_id"] for q in gap_questions}
    seen: set[str] = set()
    for answer in answers:
        req_id = answer["requirement_id"]
        if req_id not in asked:
            msg = f"{req_id!r} is not a gap question for this request"
            raise GapAnswerError(msg)
        if req_id in seen:
            msg = f"{req_id!r} was answered twice"
            raise GapAnswerError(msg)
        seen.add(req_id)
        section = answer["source_type"]
        if section not in BULLET_SECTIONS:
            msg = f"Cannot add a bullet to {section!r}"
            raise GapAnswerError(msg)
        if answer["item_id"] not in index_master(master_data).items[section]:
            msg = f"Unknown {section} item {answer['item_id']!r}"
            raise GapAnswerError(msg)
        if not answer["text"].strip():
            msg = f"The answer for {req_id!r} is empty"
            raise GapAnswerError(msg)


def _build_message(
    job_text: str, requirements: list[dict], answers: list[dict], master_data: dict,
) -> str:
    texts = {r["id"]: r["text"] for r in requirements}
    blocks = []
    for n, answer in enumerate(answers, start=1):
        item = render_item_for_prompt(
            master_data, answer["source_type"], answer["item_id"],
        )
        blocks.append(
            f"### Answer {n} (requirement_id: {answer['requirement_id']})\n"
            f"Requirement: {texts[answer['requirement_id']]}\n"
            f"Bullet goes under:\n{item}\n"
            f"Candidate's answer: {answer['text'].strip()}",
        )
    return (
        f"JOB DESCRIPTION\n{job_text}\n\n"
        f"SKILL GROUPS\n{render_skill_groups_for_prompt(master_data)}\n\n"
        "ANSWERS\n" + "\n\n".join(blocks)
    )


def _check(
    drafted: GapProposals, answers: list[dict], master_data: dict,
) -> list[str]:
    errors: list[str] = []
    wanted = {a["requirement_id"] for a in answers}
    got = [p.requirement_id for p in drafted.proposals]
    errors.extend(
        f"unknown requirement_id {r!r}" for r in dict.fromkeys(got) if r not in wanted
    )
    errors.extend(
        f"duplicate proposal for {r!r}" for r in dict.fromkeys(got) if got.count(r) > 1
    )
    errors.extend(f"no proposal for {r!r}" for r in sorted(wanted - set(got)))
    groups = index_master(master_data).skills
    for p in drafted.proposals:
        if p.change == "add_bullet" and not p.bullet.strip():
            errors.append(f"{p.requirement_id}: add_bullet needs a bullet")
        if p.skill and p.skill_group_id not in groups:
            errors.append(
                f"{p.requirement_id}: unknown skill_group_id {p.skill_group_id!r}",
            )
    return errors


def draft_proposals(
    job_text: str, requirements: list[dict], answers: list[dict], master_data: dict,
) -> list[dict]:
    """Ask the LLM to turn ``answers`` into proposals, then check them.

    Retries once with the problems listed. Raises :class:`GapAnswerError`
    when it still fails, and lets ``LLMUnavailableError`` through so the
    caller can retry on network trouble. Where each bullet goes comes from
    the user's answer, never from the LLM.
    """
    system = load_prompt("gap_answers")
    user = _build_message(job_text, requirements, answers, master_data)
    by_req = {a["requirement_id"]: a for a in answers}
    texts = {r["id"]: r["text"] for r in requirements}

    errors: list[str] = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        message = user
        if errors:
            message += (
                "\n\nYour previous answer had these problems; fix them and return "
                "the full JSON again:\n- " + "\n- ".join(errors)
            )
        raw = post_deepseek_chat(system, message, max_tokens=_MAX_TOKENS)
        try:
            drafted = GapProposals.model_validate(raw)
        except ValidationError as exc:
            errors = [f"invalid JSON shape: {e['loc']}: {e['msg']}" for e in exc.errors()[:10]]
            logger.warning("Gap proposals rejected (attempt %d): %s", attempt, errors)
            continue
        errors = _check(drafted, answers, master_data)
        if errors:
            logger.warning("Gap proposals rejected (attempt %d): %s", attempt, errors)
            continue
        return [
            {
                "id": uuid.uuid4().hex[:12],
                "requirement_id": p.requirement_id,
                "requirement_text": texts[p.requirement_id],
                "source_type": by_req[p.requirement_id]["source_type"],
                "item_id": by_req[p.requirement_id]["item_id"],
                "change": p.change,
                "bullet": p.bullet.strip() if p.change == "add_bullet" else "",
                "skill": p.skill.strip() if p.change == "add_bullet" else "",
                "skill_group_id": p.skill_group_id if p.change == "add_bullet" else "",
                "reason": p.reason,
            }
            for p in drafted.proposals
        ]

    msg = "Could not draft bullets from your answers: " + "; ".join(errors[:5])
    raise GapAnswerError(msg)


def handled_gaps_after(
    previous: list[dict], result: dict, answers: list[dict],
) -> list[dict]:
    """The earlier handled gaps plus this round's, as ``{requirement, outcome}``.

    Every gap question shown this round counts as handled: ``answered`` if the
    user wrote something, otherwise ``skipped``. Requirement text is used
    rather than ids because ids change between runs.
    """
    texts = {r["id"]: r["text"] for r in result.get("requirements", [])}
    answered = {a["requirement_id"] for a in answers}
    this_round = [
        {
            "requirement": texts[q["requirement_id"]],
            "outcome": "answered" if q["requirement_id"] in answered else "skipped",
        }
        for q in result.get("gap_questions", [])
        if q["requirement_id"] in texts
    ]
    return [*previous, *this_round]
