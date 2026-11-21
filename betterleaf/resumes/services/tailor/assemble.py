"""Build tailored resume data from the master's own text."""

from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.schemas import ResumeSelection


def _pick_items(master_items: list[dict], selected) -> list[dict]:
    by_id = {item["id"]: item for item in master_items}
    picked = []
    for sel in selected:
        item = by_id[sel.id]
        bullets = {b["id"]: b for b in item.get("bullets") or []}
        picked.append({**item, "bullets": [bullets[i] for i in sel.bullet_ids]})
    return picked


def build_tailored_resume_data(master_data: dict, selection: ResumeSelection) -> dict:
    """Copy the selected master items, in the AI's order, into new resume data.

    No text is generated: every bullet is the master's exact bullet. Name,
    contact, summary and section order come from the master unchanged.
    """
    skills_by_id = {g["id"]: g for g in master_data.get("technical_skills") or []}
    skill_groups = []
    for sel in selection.technical_skills:
        group = skills_by_id[sel.id]
        if sel.skills:
            skill_groups.append({**group, "value": ", ".join(sel.skills)})

    education_by_id = {e["id"]: e for e in master_data.get("education") or []}

    tailored = {
        **master_data,
        "experience": _pick_items(master_data.get("experience") or [], selection.experience),
        "projects": _pick_items(master_data.get("projects") or [], selection.projects),
        "achievements": _pick_items(
            master_data.get("achievements") or [], selection.achievements,
        ),
        "education": [education_by_id[i] for i in selection.education],
        "technical_skills": skill_groups,
    }
    return ResumeData.model_validate(tailored).model_dump()
