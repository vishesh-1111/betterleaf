"""Convert resume Markdown into a validated structured representation.

Uses an LLM (DeepSeek) in JSON mode to map Markdown extracted from a PDF
(:func:`betterleaf.resumes.services.extract.pdf_to_text`) onto the
:class:`ResumeData` pydantic model, then validates the result before returning
it.
"""

import json

import httpx
from django.conf import settings
from pydantic import ValidationError

from betterleaf.resumes.services.schemas import ResumeData

_HTTP_OK = 200

_SYSTEM_PROMPT = """You convert resume Markdown into structured JSON.

You are given a resume as Markdown. Extract the resume's content into a single
JSON object with exactly these top-level keys and no others:

- "name": the person's full name (string).
- "contact": an object with optional keys "phone", "email", "linkedin",
  "github", "portfolio". Only include keys that are present in the resume.
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
- Return ONLY the JSON object; no prose, no code fences."""


class ResumeParseError(Exception):
    """Raised when the LLM cannot produce a valid structured resume."""


def _build_messages(markdown: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": markdown},
    ]


def _parse_markdown(markdown: str) -> ResumeData:
    """Call DeepSeek in JSON mode and validate the output.

    Raises :class:`ResumeParseError` on transport failure, unexpected status,
    or when the returned JSON does not satisfy :class:`ResumeData`.
    """
    if not settings.DEEPSEEK_API_KEY:
        msg = "DeepSeek is not configured"
        raise ResumeParseError(msg)

    body = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": _build_messages(markdown),
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            settings.DEEPSEEK_API_URL,
            headers=headers,
            json=body,
            timeout=httpx.Timeout(300.0),
        )
    except httpx.HTTPError as exc:
        msg = f"DeepSeek request failed: {exc}"
        raise ResumeParseError(msg) from exc

    if response.status_code != _HTTP_OK:
        msg = f"DeepSeek error {response.status_code}: {response.text[:500]}"
        raise ResumeParseError(msg)

    try:
        content = response.json()["choices"][0]["message"]["content"]
        raw = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        msg = "DeepSeek returned malformed output"
        raise ResumeParseError(msg) from exc

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
