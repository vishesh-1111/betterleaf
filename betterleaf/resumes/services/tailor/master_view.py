"""Read-only views of a master resume for the tailoring flow."""

from dataclasses import dataclass
from dataclasses import field

from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.master_update import BULLET_SECTIONS


def add_missing_ids(master_data: dict) -> dict:
    """Return the master data with every item/bullet id filled in.

    Existing ids are kept, so this is safe to run repeatedly. Old masters
    (plain-string bullets, no ids) are upgraded to the current shape.
    """
    return ResumeData.model_validate(master_data).model_dump()


def _experience_line(item: dict) -> str:
    return f"{item['company']}, {item['role']} ({item['duration']})"


def _project_line(item: dict) -> str:
    stack = item.get("tech_stack")
    return f"{item['title']} | {stack}" if stack else item["title"]


def _education_line(item: dict) -> str:
    return f"{item['institution']}, {item['degree']} ({item['duration']})"


def _skill_line(item: dict) -> str:
    return f"{item['key']}: {item['value']}"


# section key -> (prompt tag, one-line description of an item)
_SECTIONS = {
    "experience": ("exp", _experience_line),
    "projects": ("proj", _project_line),
    "education": ("edu", _education_line),
    "technical_skills": ("skill", _skill_line),
    "achievements": ("ach", lambda item: item["title"]),
}


@dataclass
class MasterIndex:
    """Lookup tables used to check the LLM's answer against the master."""

    # id of any item or bullet -> the exact line the LLM saw
    lines: dict[str, str] = field(default_factory=dict)
    # section key -> item ids in that section
    items: dict[str, set[str]] = field(default_factory=dict)
    # item id -> its bullet ids
    bullets: dict[str, set[str]] = field(default_factory=dict)
    # skill group id -> the skills in its comma-separated value
    skills: dict[str, set[str]] = field(default_factory=dict)


def index_master(master_data: dict) -> MasterIndex:
    index = MasterIndex()
    for section, (_, describe) in _SECTIONS.items():
        index.items[section] = set()
        for item in master_data.get(section) or []:
            index.items[section].add(item["id"])
            index.lines[item["id"]] = describe(item)
            if section == "technical_skills":
                index.skills[item["id"]] = {
                    s.strip() for s in item["value"].split(",") if s.strip()
                }
            bullet_ids = set()
            for bullet in item.get("bullets") or []:
                bullet_ids.add(bullet["id"])
                index.lines[bullet["id"]] = bullet["text"]
            index.bullets[item["id"]] = bullet_ids
    return index


def render_master_for_prompt(master_data: dict) -> str:
    """The master as numbered plain text, e.g. ``[exp:ab12] Acme, Engineer``."""
    out: list[str] = []
    for section, (tag, describe) in _SECTIONS.items():
        items = master_data.get(section) or []
        if not items:
            continue
        out.append(f"## {section}")
        for item in items:
            out.append(f"[{tag}:{item['id']}] {describe(item)}")
            out.extend(
                f"  [b:{b['id']}] {b['text']}" for b in item.get("bullets") or []
            )
    summary = (master_data.get("summary") or {}).get("text")
    if summary:
        out.insert(0, f"## summary\n{summary}")
    return "\n".join(out)


def answer_targets(master_data: dict) -> list[dict]:
    """Where a gap answer can go: every job, project and achievement.

    Each is ``{"source_type", "item_id", "label"}``, the exact shape an answer
    sends back, so the screen can offer them in a picker.
    """
    return [
        {
            "source_type": section,
            "item_id": item["id"],
            "label": _SECTIONS[section][1](item),
        }
        for section in BULLET_SECTIONS
        for item in master_data.get(section) or []
        if item.get("id")
    ]


def render_item_for_prompt(master_data: dict, section: str, item_id: str) -> str:
    """One master item with its bullets as plain text, for the gap-answers prompt."""
    tag, describe = _SECTIONS[section]
    item = next(i for i in master_data.get(section) or [] if i["id"] == item_id)
    lines = [f"[{tag}:{item['id']}] {describe(item)}"]
    lines.extend(f"  - {b['text']}" for b in item.get("bullets") or [])
    return "\n".join(lines)


def render_skill_groups_for_prompt(master_data: dict) -> str:
    """The master's skill groups, one per line, e.g. ``[skill:ab12] Tools: Git``."""
    return "\n".join(
        f"[skill:{g['id']}] {_skill_line(g)}"
        for g in master_data.get("technical_skills") or []
    )
