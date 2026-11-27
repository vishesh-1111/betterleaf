"""Summarise a job description into a short job title."""

from betterleaf.resumes.services.llm import LLMError
from betterleaf.resumes.services.llm import load_prompt
from betterleaf.resumes.services.llm import post_deepseek_chat

_MAX_TOKENS = 60
_MAX_INPUT_CHARS = 6000  # the title is near the top; keep the call fast and cheap
_MAX_TITLE_CHARS = 90


def summarise_job_title(job_text: str) -> str:
    """Return a short title for the role in ``job_text``.

    Raises :class:`LLMError` (or its subclass) if no usable title comes back.
    """
    raw = post_deepseek_chat(
        load_prompt("job_title"),
        job_text[:_MAX_INPUT_CHARS],
        max_tokens=_MAX_TOKENS,
    )
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        msg = "Job title missing from LLM output"
        raise LLMError(msg)
    return " ".join(title.split())[:_MAX_TITLE_CHARS]
