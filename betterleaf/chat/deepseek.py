"""DeepSeek streaming client and message conversion.

The frontend sends AI SDK "model messages" (``content`` is an array of parts
like ``{"type": "text", "text": ...}``, ``{"type": "tool-call", ...}``,
``{"type": "tool-result", ...}``). DeepSeek expects the OpenAI chat format, so
we convert before POSTing. The response is streamed as SSE lines and translated
into the ``x-vercel-ai-ui-message-stream`` chunk vocabulary the browser's
``uiMessageChunkSchema`` validates.
"""

import json
import uuid

import httpx

from betterleaf.chat.tools import TOOL_SCHEMAS

SYSTEM_PROMPT = """You are a helpful LaTeX assistant. You help users write and edit LaTeX documents.

When providing LaTeX code:
- Use proper LaTeX syntax
- Explain what each part does
- Suggest best practices
- Use code blocks with ```latex for LaTeX code

You have access to the user's current document which is provided in the context.

When the user asks you to help with their document:
- Reference specific parts of their document
- Suggest improvements and fixes
- Provide complete code snippets they can use

You have tools available to directly modify the document:
- Use insert_latex to insert code at the user's cursor position
- Use replace_selection to replace selected text (only when user has selected text)
- Use find_and_replace to find and replace specific text in the document

When the user asks you to add, insert, or write LaTeX code to their document, use the insert_latex tool.
When the user asks you to replace or modify selected text, use the replace_selection tool.
When the user asks you to change, modify, or replace specific text in the document, use the find_and_replace tool.

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

    if role == "system":
        if isinstance(content, str):
            return {"role": "system", "content": content}
        return {"role": "system", "content": _text_to_string(content)}

    if role == "user":
        if isinstance(content, str):
            return {"role": "user", "content": content}
        return {"role": "user", "content": _text_to_string(content)}

    if role == "assistant":
        text_parts = []
        tool_calls = []
        if isinstance(content, str):
            text_parts.append(content)
        else:
            for part in content or []:
                ptype = part.get("type")
                if ptype == "text":
                    text_parts.append(part.get("text", ""))
                elif ptype == "tool-call":
                    tool_calls.append(
                        {
                            "id": part.get("toolCallId"),
                            "type": "function",
                            "function": {
                                "name": part.get("toolName"),
                                "arguments": json.dumps(part.get("input") or {}),
                            },
                        },
                    )
        result = {"role": "assistant", "content": "".join(text_parts)}
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result

    if role == "tool":
        # A role:"tool" message carries tool-result parts keyed by toolCallId.
        results = []
        if isinstance(content, dict):
            content = [content]
        for part in content or []:
            ptype = part.get("type")
            if ptype in ("tool-result", "tool-error"):
                output = part.get("output", part.get("error"))
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": part.get("toolCallId"),
                        "content": (
                            output if isinstance(output, str) else json.dumps(output)
                        ),
                    },
                )
        return results  # list of tool messages

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
        if isinstance(item, list):
            converted.extend(item)
        elif item.get("role") == "system" and item.get("content", "").strip():
            converted.append(item)
        elif item.get("role") != "system":
            converted.append(item)

    result = [{"role": "system", "content": system}] if system else []
    result.extend(converted)
    return result


async def stream_chat(
    messages: list[dict],
    tools: dict,
    api_url: str,
    model: str,
    api_key: str,
):
    """Stream DeepSeek's OpenAI-compatible response.

    Yields UI-message-stream chunks (``start``/``text-*``/``tool-input-*``)
    followed by a final metadata dict as the last item:
    ``{"tool_calls": [...], "finish_reason": "..."}``. The view uses that final
    dict to decide tool execution and whether to loop. ``finish`` is emitted by
    the caller, not here.
    """
    request_body: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        request_body["tools"] = TOOL_SCHEMAS

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    message_id = str(uuid.uuid4())
    text_id = str(uuid.uuid4())
    started = False
    text_started = False
    text_ended = False
    finish_reason = None

    # Buffered tool-call state (indexed like OpenAI stream fragments).
    tool_calls: dict[int, dict] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=300.0)) as client:
        try:
            async with client.stream(
                "POST", api_url, headers=headers, json=request_body,
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode("utf-8", "replace")
                    yield {
                        "tool_calls": [],
                        "finish_reason": "error",
                        "error": f"DeepSeek error {response.status_code}: {body[:500]}",
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
                        if not started:
                            started = True
                            yield {"type": "start", "messageId": message_id}
                        if not text_started:
                            text_started = True
                            yield {"type": "text-start", "id": text_id}
                        yield {"type": "text-delta", "id": text_id, "delta": content}

                    for tc in delta.get("tool_calls") or []:
                        index = tc.get("index", 0)
                        entry = tool_calls.setdefault(
                            index,
                            {
                                "id": tc.get("id"),
                                "name": "",
                                "arguments": "",
                                "started": False,
                            },
                        )
                        if tc.get("id"):
                            entry["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            entry["name"] = fn["name"]
                        if fn.get("arguments"):
                            if not entry["started"]:
                                entry["started"] = True
                                yield {
                                    "type": "tool-input-start",
                                    "toolCallId": entry["id"],
                                    "toolName": entry["name"],
                                }
                            entry["arguments"] += fn["arguments"]
                            yield {
                                "type": "tool-input-delta",
                                "toolCallId": entry["id"],
                                "inputTextDelta": fn["arguments"],
                            }
        except httpx.HTTPError as exc:
            yield {"tool_calls": [], "finish_reason": "error", "error": str(exc)}
            return

    # Close text first, then finalize any tool inputs, then hand control back.
    if text_started and not text_ended:
        yield {"type": "text-end", "id": text_id}

    completed = []
    for idx in sorted(tool_calls):
        entry = tool_calls[idx]
        try:
            input_args = (
                json.loads(entry["arguments"]) if entry["arguments"].strip() else {}
            )
        except json.JSONDecodeError:
            input_args = {}
        if not entry["started"]:
            yield {
                "type": "tool-input-start",
                "toolCallId": entry["id"],
                "toolName": entry["name"],
            }
        yield {
            "type": "tool-input-available",
            "toolCallId": entry["id"],
            "toolName": entry["name"],
            "input": input_args,
        }
        completed.append(
            {
                "id": entry["id"],
                "name": entry["name"],
                "input": input_args,
            },
        )

    yield {"tool_calls": completed, "finish_reason": finish_reason or "stop"}
