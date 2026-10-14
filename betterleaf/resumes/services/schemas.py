"""Pydantic models for the structured resume representation.

The LLM returns a JSON document that matches :class:`ResumeData` and its
nested models. These models are the single source of truth for that shape and
are used to validate the model output before it reaches the rest of the app.
"""

from pydantic import BaseModel
from pydantic import Field

# Canonical set of section keys a resume may carry. NOT a rendering order; the
# order sections appear in is dynamic and captured via ``section_order``.
SECTION_KEYS = (
    "education",
    "experience",
    "projects",
    "technical_skills",
    "achievements",
)


class ContactInfo(BaseModel):
    """Contact details; every field is optional."""

    phone: str | None = None
    email: str | None = None
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Experience(BaseModel):
    company: str = Field(description="Name of the company")
    duration: str = Field(description="Duration, e.g. 'Jan 2021 - Mar 2023'")
    role: str = Field(description="Role/title, e.g. 'AI Engineer'")
    bullets: list[str] = Field(default_factory=list)


class TechnicalSkill(BaseModel):
    """One skill group: a category key and comma-separated values."""

    key: str = Field(description="Category, e.g. 'Systems & Tooling'")
    value: str = Field(
        description="Comma-separated values, e.g. 'Linux, Windows, GCC, CMake, Git'",
    )


class Education(BaseModel):
    institution: str = Field(description="College/school name")
    duration: str = Field(description="Duration, e.g. '2017 - 2021'")
    degree: str = Field(description="Degree or role, e.g. 'B.Tech, Computer Science'")


class Project(BaseModel):
    title: str
    github: str | None = Field(default=None, description="Project github link")
    deployed: str | None = Field(default=None, description="Project deployed link")
    tech_stack: str = Field(
        default="", description="Comma-separated tech stack words",
    )
    bullets: list[str] = Field(default_factory=list)


class Achievement(BaseModel):
    title: str = Field(description="Achievement title")
    bullets: list[str] = Field(default_factory=list)


class ResumeData(BaseModel):
    name: str
    contact: ContactInfo = Field(default_factory=ContactInfo)
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
