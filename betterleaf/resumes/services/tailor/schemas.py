"""Models for the tailoring analysis the LLM returns.

The LLM never writes resume text. It scores the job's requirements against the
master resume and returns a *selection* of the master's own items, by id.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

# Tags the prompt shows before each id, e.g. ``[exp:ab12]``. Models sometimes
# copy the tag into the id ("exp:ab12"); drop it so the id still matches.
_ID_TAGS = {"exp", "proj", "edu", "skill", "ach", "b"}


def strip_id_tag(value):
    if isinstance(value, str) and ":" in value:
        tag, _, rest = value.partition(":")
        if tag in _ID_TAGS:
            return rest
    return value

Importance = Literal["must_have", "nice_to_have"]
Coverage = Literal["met", "partial", "not_met"]


class Evidence(BaseModel):
    source_id: str = Field(description="Id of the master item or bullet")
    quote: str = Field(description="Exact words from that line")

    @field_validator("source_id", mode="before")
    @classmethod
    def _strip_tag(cls, value):
        return strip_id_tag(value)


class Requirement(BaseModel):
    id: str
    text: str
    importance: Importance = "must_have"
    priority: int = Field(default=1, ge=1, description="1 = most important")
    evidence: list[Evidence] = Field(default_factory=list)
    status: Coverage
    rationale: str = ""


class GapQuestion(BaseModel):
    requirement_id: str
    question: str


class SelectedItem(BaseModel):
    """A master item to keep, with its kept bullets in display order."""

    id: str
    bullet_ids: list[str] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def _strip_tag(cls, value):
        return strip_id_tag(value)

    @field_validator("bullet_ids", mode="before")
    @classmethod
    def _strip_bullet_tags(cls, value):
        return [strip_id_tag(v) for v in value] if isinstance(value, list) else value


class SelectedSkillGroup(BaseModel):
    id: str
    skills: list[str] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def _strip_tag(cls, value):
        return strip_id_tag(value)


class ResumeSelection(BaseModel):
    experience: list[SelectedItem] = Field(default_factory=list)
    projects: list[SelectedItem] = Field(default_factory=list)
    achievements: list[SelectedItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    technical_skills: list[SelectedSkillGroup] = Field(default_factory=list)

    @field_validator("education", mode="before")
    @classmethod
    def _strip_education_tags(cls, value):
        return [strip_id_tag(v) for v in value] if isinstance(value, list) else value


class TailoringAnalysis(BaseModel):
    requirements: list[Requirement]
    experience_required: str = Field(
        default="Not Mentioned",
        description='Years of experience the job asks for, e.g. "2 years"',
    )
    gap_questions: list[GapQuestion] = Field(default_factory=list)
    selection: ResumeSelection = Field(default_factory=ResumeSelection)


GapChange = Literal["add_bullet", "no_change"]


class GapProposal(BaseModel):
    """One AI-drafted change for one answered gap."""

    requirement_id: str
    change: GapChange
    bullet: str = ""
    skill: str = ""
    skill_group_id: str = ""
    reason: str = ""

    @field_validator("skill_group_id", mode="before")
    @classmethod
    def _strip_tag(cls, value):
        return strip_id_tag(value)


class GapProposals(BaseModel):
    proposals: list[GapProposal]
