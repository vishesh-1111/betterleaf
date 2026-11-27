"""Score a job description against a master resume and pick what to keep."""

import logging
import re
import unicodedata

from pydantic import ValidationError

from betterleaf.resumes.services.llm import load_prompt
from betterleaf.resumes.services.llm import post_deepseek_chat
from betterleaf.resumes.services.tailor.master_view import MasterIndex
from betterleaf.resumes.services.tailor.master_view import index_master
from betterleaf.resumes.services.tailor.master_view import render_master_for_prompt
from betterleaf.resumes.services.tailor.schemas import TailoringAnalysis

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4000
_MAX_ATTEMPTS = 2  # first try plus one retry with the errors fed back
MAX_SKILLS_PER_GROUP = 10


class TailoringError(Exception):
    """The LLM could not produce a valid analysis."""


def _check_selection(analysis: TailoringAnalysis, index: MasterIndex) -> list[str]:
    errors: list[str] = []
    selection = analysis.selection
    for section in ("experience", "projects", "achievements"):
        for item in getattr(selection, section):
            if item.id not in index.items[section]:
                errors.append(f"selection.{section}: unknown item id {item.id!r}")
                continue
            for bullet_id in item.bullet_ids:
                if bullet_id not in index.bullets[item.id]:
                    errors.append(
                        f"selection.{section}: bullet {bullet_id!r} is not in item {item.id!r}",
                    )
    errors.extend(
        f"selection.education: unknown id {edu_id!r}"
        for edu_id in selection.education
        if edu_id not in index.items["education"]
    )
    for group in selection.technical_skills:
        if group.id not in index.skills:
            errors.append(f"selection.technical_skills: unknown group id {group.id!r}")
            continue
        errors.extend(
            f"selection.technical_skills: {skill!r} is not in group {group.id!r}"
            for skill in group.skills
            if skill not in index.skills[group.id]
        )
    return errors


def _check_requirements(analysis: TailoringAnalysis, index: MasterIndex) -> list[str]:
    errors: list[str] = []
    if not analysis.requirements:
        errors.append("requirements: none returned")
    seen: set[str] = set()
    for req in analysis.requirements:
        if req.id in seen:
            errors.append(f"requirements: duplicate id {req.id!r}")
        seen.add(req.id)
        if req.status != "not_met" and not req.evidence:
            errors.append(f"{req.id}: status {req.status!r} needs evidence")
        errors.extend(
            f"{req.id}: unknown evidence id {ev.source_id!r}"
            for ev in req.evidence
            if ev.source_id not in index.lines
        )
    errors.extend(
        f"gap_questions: unknown requirement id {q.requirement_id!r}"
        for q in analysis.gap_questions
        if q.requirement_id not in seen
    )
    return errors


def _normalise(text: str) -> str:
    """Fold dash/quote/whitespace/case differences the LLM tends to introduce."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    return " ".join(text.split()).casefold()


def repair_quotes(analysis: TailoringAnalysis, index: MasterIndex) -> None:
    """Make every evidence quote real master text.

    The quote is display-only; ``source_id`` is what is trusted. A quote that
    matches loosely (dashes, quotes, spacing, case) is kept; any other is
    replaced by the cited line itself, so a paraphrase never fails the request.
    """
    for req in analysis.requirements:
        for ev in req.evidence:
            line = index.lines.get(ev.source_id)
            if line is not None and _normalise(ev.quote) not in _normalise(line):
                ev.quote = line


def check_analysis(analysis: TailoringAnalysis, master_data: dict) -> list[str]:
    """Return every way the analysis disagrees with the master (empty = valid)."""
    index = index_master(master_data)
    repair_quotes(analysis, index)
    return _check_requirements(analysis, index) + _check_selection(analysis, index)


def tidy_gap_questions(analysis: TailoringAnalysis) -> None:
    """Keep only questions for ``not_met`` requirements, must-haves first."""
    by_id = {r.id: r for r in analysis.requirements}
    kept = [
        q for q in analysis.gap_questions if by_id[q.requirement_id].status == "not_met"
    ]
    kept.sort(
        key=lambda q: (
            by_id[q.requirement_id].importance != "must_have",
            by_id[q.requirement_id].priority,
        ),
    )
    analysis.gap_questions = kept


def cap_skills(analysis: TailoringAnalysis) -> None:
    """Keep each skill group to its first ``MAX_SKILLS_PER_GROUP`` (the AI's order)."""
    for group in analysis.selection.technical_skills:
        group.skills = group.skills[:MAX_SKILLS_PER_GROUP]


def _render_handled_gaps(handled_gaps: list[dict]) -> str:
    return "\n".join(f"- {g['requirement']} ({g['outcome']})" for g in handled_gaps)


def analyse_job_fit(
    job_text: str, master_data: dict, handled_gaps: list[dict] | None = None,
) -> TailoringAnalysis:
    """Ask the LLM how well ``master_data`` covers ``job_text``, then check it.

    Retries once with the problems listed if the answer fails the checks.
    Raises :class:`TailoringError` when it still does not pass, and lets
    :class:`~betterleaf.resumes.services.llm.LLMUnavailableError` through so
    the caller can retry on network trouble. ``handled_gaps`` lists gaps the
    user already answered or skipped, so they are not asked again.
    """
    system = load_prompt("tailor")
    user = (
        f"JOB DESCRIPTION\n{job_text}\n\n"
        f"MASTER RESUME\n{render_master_for_prompt(master_data)}"
    )
    if handled_gaps:
        user += f"\n\nALREADY HANDLED\n{_render_handled_gaps(handled_gaps)}"

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
            analysis = TailoringAnalysis.model_validate(raw)
        except ValidationError as exc:
            errors = [f"invalid JSON shape: {e['loc']}: {e['msg']}" for e in exc.errors()[:10]]
            logger.warning("Tailoring answer rejected (attempt %d): %s", attempt, errors)
            continue
        errors = check_analysis(analysis, master_data)
        if not errors:
            tidy_gap_questions(analysis)
            cap_skills(analysis)
            return analysis
        logger.warning("Tailoring answer rejected (attempt %d): %s", attempt, errors)

    msg = "Could not analyse this job description: " + "; ".join(errors[:5])
    raise TailoringError(msg)
