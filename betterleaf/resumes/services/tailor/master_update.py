"""Write accepted gap-answer proposals into the master resume.

Add-only: a new bullet on an existing job, project or achievement, plus an
optional skill word in an existing skill group. Nothing else is touched.
"""

import copy

from betterleaf.resumes.services.schemas import new_id

# Sections a bullet may be added to.
BULLET_SECTIONS = ("experience", "projects", "achievements")


class MasterUpdateError(Exception):
    """A proposal points at something that is not in the master."""


def _add_skill(master: dict, group_id: str, skill: str) -> None:
    group = next(
        (g for g in master.get("technical_skills") or [] if g["id"] == group_id),
        None,
    )
    if group is None:
        msg = f"Unknown skill group {group_id!r}"
        raise MasterUpdateError(msg)
    current = [s.strip() for s in group["value"].split(",") if s.strip()]
    if skill.lower() not in {s.lower() for s in current}:
        group["value"] = ", ".join([*current, skill])


def apply_proposals(master_data: dict, entries: list[dict]) -> dict:
    """Return a copy of the master with every entry applied.

    Each entry is ``{"source_type", "item_id", "bullet", "skill", "skill_group_id"}``.
    ``skill`` and ``skill_group_id`` are optional and must come as a pair.
    The input is left unchanged, and nothing is applied if any entry is bad.
    """
    master = copy.deepcopy(master_data)
    for entry in entries:
        section = entry.get("source_type")
        if section not in BULLET_SECTIONS:
            msg = f"Cannot add a bullet to section {section!r}"
            raise MasterUpdateError(msg)
        item = next(
            (i for i in master.get(section) or [] if i["id"] == entry.get("item_id")),
            None,
        )
        if item is None:
            msg = f"Unknown {section} item {entry.get('item_id')!r}"
            raise MasterUpdateError(msg)
        text = (entry.get("bullet") or "").strip()
        if not text:
            msg = "A bullet cannot be empty"
            raise MasterUpdateError(msg)
        item.setdefault("bullets", []).append({"id": new_id(), "text": text})

        skill = (entry.get("skill") or "").strip()
        group_id = entry.get("skill_group_id")
        if skill and group_id:
            _add_skill(master, group_id, skill)
    return master
