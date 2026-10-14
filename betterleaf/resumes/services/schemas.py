"""Pydantic models for the structured resume representation.

The LLM returns a JSON document that matches :class:`ResumeData` and its
nested models. These models are the single source of truth for that shape and
are used to validate the model output before it reaches the rest of the app.

Every list item (and every bullet) carries a stable ``id``. IDs drive the
server-side diff between an old and a rewritten resume, so they must persist
across LLM round-trips: the LLM is told to preserve the IDs of existing items
and omit them for new ones, and the ``default_factory`` assigns fresh IDs to
whatever it omits.
"""

import uuid

from pydantic import BaseModel
from pydantic import Field

# Canonical set of section keys a resume may carry. NOT a rendering order; the
# order sections appear in is dynamic and captured via ``section_order``.
SECTION_KEYS = (
    "summary",
    "education",
    "experience",
    "projects",
    "technical_skills",
    "achievements",
)


def new_id() -> str:
    """Return a short, URL-safe, collision-resistant item ID."""
    return uuid.uuid4().hex[:8]


class Bullet(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str


class Summary(BaseModel):
    text: str = Field(description="A short summary paragraph of the resume")


class ContactInfo(BaseModel):
    """Contact details; every field is optional."""

    phone: str | None = None
    email: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Experience(BaseModel):
    id: str = Field(default_factory=new_id)
    company: str = Field(description="Name of the company")
    duration: str = Field(description="Duration, e.g. 'Jan 2021 - Mar 2023'")
    role: str = Field(description="Role/title, e.g. 'AI Engineer'")
    bullets: list[Bullet] = Field(default_factory=list)


class TechnicalSkill(BaseModel):
    """One skill group: a category key and comma-separated values."""

    id: str = Field(default_factory=new_id)
    key: str = Field(description="Category, e.g. 'Systems & Tooling'")
    value: str = Field(
        description="Comma-separated values, e.g. 'Linux, Windows, GCC, CMake, Git'",
    )


class Education(BaseModel):
    id: str = Field(default_factory=new_id)
    institution: str = Field(description="College/school name")
    duration: str = Field(description="Duration, e.g. '2017 - 2021'")
    degree: str = Field(description="Degree or role, e.g. 'B.Tech, Computer Science'")


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    github: str | None = Field(default=None, description="Project github link")
    deployed: str | None = Field(default=None, description="Project deployed link")
    tech_stack: str = Field(
        default="",
        description="Comma-separated tech stack words",
    )
    bullets: list[Bullet] = Field(default_factory=list)


class Achievement(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str = Field(description="Achievement title")
    bullets: list[Bullet] = Field(default_factory=list)


class ResumeData(BaseModel):
    name: str
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: Summary | None = Field(default=None)
    experience: list[Experience] = Field(default_factory=list)
    technical_skills: list[TechnicalSkill] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    achievements: list[Achievement] = Field(default_factory=list)
    section_order: list[str] = Field(
        default_factory=list,
        description=(
            "Optional ordered list of section keys as they should render. "
            "Inferred from the source key order when absent."
        ),
    )
