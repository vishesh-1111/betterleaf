"""Rewrite a structured resume using an LLM.

Unlike :mod:`betterleaf.resumes.services.parser` (Markdown -> JSON), this
module asks DeepSeek to *rewrite* an existing, validated
:class:`ResumeData` in response to a user prompt, returning a full new
:class:`ResumeData`. The server then diffs old vs. new by ID (see
:mod:`betterleaf.resumes.services.proposals`).

Critical contract with the model: every list item and bullet already carries
an ``id``. The model MUST preserve the ``id`` of any item it keeps and MUST
omit ``id`` entirely for any item it creates; ``default_factory`` assigns IDs
to the omitted ones. This is what keeps the subsequent diff by ID correct.
"""

import json

import httpx
from django.conf import settings
from pydantic import ValidationError

from betterleaf.resumes.services.parser import ResumeParseError
from betterleaf.resumes.services.schemas import SECTION_KEYS
from betterleaf.resumes.services.schemas import ResumeData

_HTTP_OK = 200

_SYSTEM_PROMPT = """You rewrite a structured resume in response to a user request.

You are given a resume as a JSON object plus the user's instruction. Return a
single JSON object with the SAME shape, applying the user's requested changes
to the relevant content and leaving everything else untouched.

Shape (same top-level keys, nothing else):
- "name" (string), "contact" (object of optional "phone"/"email"/"linkedin"/
  "github"/"portfolio"), "summary" ({"text": ...} or null).
- "experience": list of {"company", "duration", "role", "bullets"}.
- "technical_skills": list of {"key", "value"}.
- "education": list of {"institution", "duration", "degree"}.
- "projects": list of {"title", "github", "deployed", "tech_stack", "bullets"}.
- "achievements": list of {"title", "bullets"}.
- "bullets" is always a list of {"text": ...} objects.

IDs — CRITICAL:
- Every list item and every bullet has an "id" (a short hex string).
- For ANY item or bullet you keep or edit, keep its "id" EXACTLY as given.
- For ANY item or bullet you create, OMIT the "id" field entirely (the server
  assigns a new id).

Rules:
- Only change what the user asked. Preserve all other content and wording.
- Do not invent facts, names, dates, links, or skills.
- Return ONLY the JSON object; no prose, no code fences."""


def _build_messages(current: ResumeData, prompt: str) -> list[dict]:
    user_text = (
        "Current resume JSON:\n"
        + json.dumps(current.model_dump(), ensure_ascii=False)
        + "\n\nInstruction:\n"
        + prompt
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def _call_llm(current: ResumeData, prompt: str) -> ResumeData:
    """Call DeepSeek in JSON mode and validate the rewritten resume."""
    if not settings.DEEPSEEK_API_KEY:
        msg = "DeepSeek is not configured"
        raise ResumeParseError(msg)

    body = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": _build_messages(current, prompt),
        "response_format": {"type": "json_object"},
        "max_tokens": 2000,
        "stream": False,
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

    section_order = [k for k in raw if k in SECTION_KEYS and raw.get(k)]
    if section_order:
        raw["section_order"] = section_order

    try:
        return ResumeData.model_validate(raw)
    except ValidationError as exc:
        msg = f"Invalid resume structure: {exc}"
        raise ResumeParseError(msg) from exc


def rewrite_resume(current: ResumeData, prompt: str) -> ResumeData:
    """Rewrite ``current`` per ``prompt``, returning a validated new model."""
    if not prompt.strip():
        msg = "No rewrite instruction provided"
        raise ResumeParseError(msg)
    return _call_llm(current, prompt)
