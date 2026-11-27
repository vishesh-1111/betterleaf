"""Convert resume Markdown into a validated structured representation.

Uses an LLM (DeepSeek) in JSON mode to map Markdown extracted from a PDF
(:func:`betterleaf.resumes.services.extract.pdf_to_text`) onto the
:class:`ResumeData` pydantic model, then validates the result before returning
it.
"""

from pydantic import ValidationError

from betterleaf.resumes.services.llm import LLMError
from betterleaf.resumes.services.llm import post_deepseek_chat
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.schemas import SECTION_KEYS

_SYSTEM_PROMPT = """You convert resume Markdown into structured JSON.

You are given a resume as Markdown. Extract the resume's content into a single
JSON object with exactly these top-level keys and no others:

- "name": the person's full name (string).
- "contact": an object with optional keys "phone", "email", "linkedin",
  "github", "portfolio". Only include keys that are present in the resume.
- "summary": an object with a single key "text" (a short paragraph) OR null
  when the resume has no summary section.
- "experience": a list of objects, each with "company", "duration", "role"
  (all strings) and "bullets" (list of strings describing work).
- "technical_skills": a list of objects, each with "key" (a category, e.g.
  "Systems & Tooling") and "value" (comma-separated items, e.g.
  "Linux, Windows, GCC, CMake, Git"). Split grouped skills into one entry per
  category.
- "education": a list of objects, each with "institution", "duration",
  "degree".
- "projects": a list of objects, each with "title", "github" (link or null),
  "deployed" (link or null), "tech_stack" (comma-separated words), and
  "bullets" (list of strings highlighting the project).
- "achievements": a list of objects, each with "title" and "bullets".

Rules:
- Do not invent facts, names, dates, links, or skills that are not in the
  Markdown. If something is absent, use an empty list or null.
- Preserve the original wording from the resume for bullets where possible.
- For projects, put "Source Code"/repository links only in "github" and the
  live link only in "deployed"; do not repeat them as bullets.
- Preserve bold emphasis: keep Markdown **bold** markers around the same words
  in bullets and the summary exactly as they appear in the input. Do not add new bold.
- Return ONLY the JSON object; no prose, no code fences."""


class ResumeParseError(Exception):
    """Raised when the LLM cannot produce a valid structured resume."""


def _parse_markdown(markdown: str) -> ResumeData:
    """Ask DeepSeek to structure the resume Markdown and validate the output.

    Raises :class:`ResumeParseError` on LLM failure or when the returned JSON
    does not satisfy :class:`ResumeData`.
    """
    try:
        raw = post_deepseek_chat(_SYSTEM_PROMPT, markdown, max_tokens=6000)
    except LLMError as exc:
        raise ResumeParseError(str(exc)) from exc

    # Capture the LLM's section ordering (JSON key order) so rendering can
    # follow it instead of a fixed template order.
    section_order = [k for k in raw if k in SECTION_KEYS and raw.get(k)]
    if section_order:
        raw["section_order"] = section_order

    try:
        return ResumeData.model_validate(raw)
    except ValidationError as exc:
        msg = f"Invalid resume structure: {exc}"
        raise ResumeParseError(msg) from exc


def extract_resume(markdown: str) -> ResumeData:
    """Convert resume Markdown into a structured, validated :class:`ResumeData`.

    ``markdown`` typically comes from
    :func:`betterleaf.resumes.services.extract.pdf_to_text`.
    """
    if not markdown.strip():
        msg = "No resume Markdown provided"
        raise ResumeParseError(msg)
    return _parse_markdown(markdown)
