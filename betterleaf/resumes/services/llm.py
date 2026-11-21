"""DeepSeek transport and prompt loading, shared by the resume LLM tasks.

Task-level functions (``extract_resume``, ``analyse_job_fit``) own their
prompts and validation; this module only knows how to talk to DeepSeek.
"""

import json
from pathlib import Path

import httpx
from django.conf import settings

_HTTP_OK = 200
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLMError(Exception):
    """The LLM call failed or returned something unusable."""


class LLMUnavailableError(LLMError):
    """Network trouble or a server-side error; worth retrying later."""


def load_prompt(name: str) -> str:
    """Return the text of ``prompts/<name>.md``."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def post_deepseek_chat(system: str, user: str, max_tokens: int) -> dict:
    """Send one chat turn to DeepSeek in JSON mode and return the parsed object.

    Raises :class:`LLMUnavailableError` on transport failure or a 5xx, and
    :class:`LLMError` on any other bad status or malformed output.
    """
    if not settings.DEEPSEEK_API_KEY:
        msg = "DeepSeek is not configured"
        raise LLMError(msg)

    body = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        # Cap output; without this the model pads completion tokens, adding latency.
        "max_tokens": max_tokens,
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
        raise LLMUnavailableError(msg) from exc

    if response.status_code != _HTTP_OK:
        msg = f"DeepSeek error {response.status_code}: {response.text[:500]}"
        error_cls = LLMUnavailableError if response.status_code >= 500 else LLMError  # noqa: PLR2004
        raise error_cls(msg)

    try:
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        msg = "DeepSeek returned malformed output"
        raise LLMError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "DeepSeek returned malformed output"
        raise LLMError(msg)
    return parsed
