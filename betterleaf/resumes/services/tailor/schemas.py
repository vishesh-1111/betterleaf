"""Models for the tailoring analysis the LLM returns.

The LLM never writes resume text. It scores the job's requirements against the
master resume and returns a *selection* of the master's own items, by id.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

Importance = Literal["must_have", "nice_to_have"]
Coverage = Literal["met", "partial", "not_met"]


class Evidence(BaseModel):
    source_id: str = Field(description="Id of the master item or bullet")
    quote: str = Field(description="Exact words from that line")


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


class SelectedSkillGroup(BaseModel):
    id: str
    skills: list[str] = Field(default_factory=list)


class ResumeSelection(BaseModel):
    experience: list[SelectedItem] = Field(default_factory=list)
    projects: list[SelectedItem] = Field(default_factory=list)
    achievements: list[SelectedItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    technical_skills: list[SelectedSkillGroup] = Field(default_factory=list)


class TailoringAnalysis(BaseModel):
    requirements: list[Requirement]
    gap_questions: list[GapQuestion] = Field(default_factory=list)
    selection: ResumeSelection = Field(default_factory=ResumeSelection)
