"""DeepSeek streaming client and message conversion.

The frontend sends AI SDK "model messages" (``content`` is an array of parts
like ``{"type": "text", "text": ...}``). DeepSeek expects the OpenAI chat
format, so we convert before POSTing. The response is streamed as SSE lines and
translated into the ``x-vercel-ai-ui-message-stream`` chunk vocabulary the
browser's ``uiMessageChunkSchema`` validates.

The assistant has no tools: it returns the full updated LaTeX document in a
fenced code block, and the view extracts and compiles that output.
"""

import json
import uuid

import httpx

SYSTEM_PROMPT = """You are a LaTeX document assistant. You help users write and edit their entire LaTeX document.

You are given the user's current document in the context. When the user asks you to write, edit, add, or change content in their document, you MUST respond with the COMPLETE, updated LaTeX document — never a fragment or a patch.

Rules:
- Return the full LaTeX source wrapped in a single fenced code block: ```latex ... ```
- Do not add prose before or after the code block unless the user explicitly asks for an explanation.
- The code block must contain the entire document, compiling as-is with a standard LaTeX class.
- Preserve and incorporate all existing content that the user did not ask to change.
- Do not invent or hallucinate content the user never provided or requested.

You have NO tools. Your only way to change the document is to output the full updated LaTeX in the code block.

Common tasks you help with:
- Writing mathematical equations
- Document structure (sections, chapters)
- Tables and figures
- Bibliography and citations
- Formatting and styling
- Package recommendations
- Debugging LaTeX errors"""


def _text_to_string(parts) -> str:
    """Collapse AI SDK text parts into a single string (for user/system)."""
    chunks = []
    for part in parts or []:
        if isinstance(part, dict) and part.get("type") == "text":
            chunks.append(part.get("text", ""))
        elif isinstance(part, str):
            chunks.append(part)
    return "".join(chunks)


def _convert_message(message: dict) -> dict | None:
    """Convert one AI SDK model message into OpenAI chat format."""
    role = message.get("role")
    content = message.get("content")

    if role in ("system", "user"):
        if isinstance(content, str):
            return {"role": role, "content": content}
        return {"role": role, "content": _text_to_string(content)}

    if role == "assistant":
        if isinstance(content, str):
            text = content
        else:
            text = "".join(
                part.get("text", "")
                for part in content or []
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return {"role": "assistant", "content": text}

    return None


def convert_messages_to_openai(messages: list[dict], system: str) -> list[dict]:
    """Flatten AI SDK model messages into DeepSeek's OpenAI-format list."""
    converted: list[dict] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        item = _convert_message(message)
        if item is None:
            continue
        if item.get("role") == "system" and item.get("content", "").strip():
            converted.append(item)
        elif item.get("role") != "system":
            converted.append(item)

    result = [{"role": "system", "content": system}] if system else []
    result.extend(converted)
    return result


async def stream_chat(
    messages: list[dict],
    api_url: str,
    model: str,
    api_key: str,
):
    """Stream DeepSeek's OpenAI-compatible response.

    Yields UI-message-stream text chunks (``start``/``text-*``). The final item
    is a metadata dict ``{"finish_reason": "...", "full_text": "..."}`` carrying
    the complete concatenated assistant text, which the caller uses to extract
    the LaTeX document. ``finish`` is emitted by the caller, not here.
    """
    request_body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        # Force thinking mode off regardless of model default.
        # "reasoning_effort": "none",
        # "thinking": {"type": "disabled"},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    message_id = str(uuid.uuid4())
    text_id = str(uuid.uuid4())
    started = False
    text_started = False
    finish_reason = None
    full_text: list[str] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=300.0)) as client:
        try:
            async with client.stream(
                "POST", api_url, headers=headers, json=request_body,
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    yield {
                        "finish_reason": "error",
                        "error": f"DeepSeek error {response.status_code}: {body[:500]}",
                        "full_text": "",
                    }
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break

                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta") or {}
                    finish_reason = choice.get("finish_reason") or finish_reason

                    content = delta.get("content")
                    if content:
                        full_text.append(content)
                        if not started:
                            started = True
                            yield {"type": "start", "messageId": message_id}
                        if not text_started:
                            text_started = True
                            yield {"type": "text-start", "id": text_id}
                        yield {"type": "text-delta", "id": text_id, "delta": content}
        except httpx.HTTPError as exc:
            yield {
                "finish_reason": "error",
                "error": str(exc),
                "full_text": "".join(full_text),
            }
            return

    if text_started:
        yield {"type": "text-end", "id": text_id}

    yield {"finish_reason": finish_reason or "stop", "full_text": "".join(full_text)}
