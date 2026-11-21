"""Pydantic models for the structured resume representation.

The LLM returns a JSON document that matches :class:`ResumeData` and its
nested models. These models are the single source of truth for that shape and
are used to validate the model output before it reaches the rest of the app.
"""

import uuid

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

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
    """Short unique id, assigned by code (never the LLM)."""
    return uuid.uuid4().hex[:12]


class Bullet(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str


class _WithBullets(BaseModel):
    """Mixin: ``bullets`` accepts plain strings and wraps them with ids."""

    bullets: list[Bullet] = Field(default_factory=list)

    @field_validator("bullets", mode="before")
    @classmethod
    def _wrap_bullets(cls, value):
        return [{"text": b} if isinstance(b, str) else b for b in value or []]


class Summary(BaseModel):
    text: str = Field(description="A short summary paragraph of the resume")


class ContactInfo(BaseModel):
    """Contact details; every field is optional."""

    phone: str | None = None
    email: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Experience(_WithBullets):
    id: str = Field(default_factory=new_id)
    company: str = Field(description="Name of the company")
    duration: str = Field(description="Duration, e.g. 'Jan 2021 - Mar 2023'")
    role: str = Field(description="Role/title, e.g. 'AI Engineer'")


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


class Project(_WithBullets):
    id: str = Field(default_factory=new_id)
    title: str
    github: str | None = Field(default=None, description="Project github link")
    deployed: str | None = Field(default=None, description="Project deployed link")
    tech_stack: str = Field(
        default="", description="Comma-separated tech stack words",
    )


class Achievement(_WithBullets):
    id: str = Field(default_factory=new_id)
    title: str = Field(description="Achievement title")


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
