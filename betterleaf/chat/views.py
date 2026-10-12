import json

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.chat import deepseek
from betterleaf.chat.serializers import ChatRequestSerializer
from betterleaf.chat.tools import TOOL_EXECUTORS
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.models import Resume

MAX_STEPS = 10


def _build_system_prompt(system: str, resume: Resume | None) -> str:
    parts = [deepseek.SYSTEM_PROMPT]
    if system:
        parts.append(system)
    elif resume is not None:
        parts.append(
            f'You are editing a LaTeX document named "{resume.title}".\n\n'
            "Here is the current content of the document:\n\n"
            f"```latex\n{resume.main_tex}\n```"
        )
    return "\n\n".join(parts)


def _to_ui_messages(messages: list[dict], system: str, resume: Resume | None) -> list[dict]:
    """Resolve the view's final system prompt and prepend it to the message list."""
    full_system = _build_system_prompt(system, resume)
    return deepseek.convert_messages_to_openai(messages, full_system)


class ChatStreamView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not settings.DEEPSEEK_API_KEY:
            return Response(
                {"error": "DeepSeek not configured"}, status=503,
            )

        workspace = get_workspace(request)
        if workspace is None:
            return Response({"error": "No workspace available"}, status=400)

        resume = None
        resume_id = data.get("resume_id")
        if resume_id:
            resume = workspace.resumes.filter(id=resume_id).first()
            if resume is None:
                return Response({"error": "Resume not found"}, status=404)
        else:
            resume = workspace.resumes.order_by("-updated_at").first()
        if resume is None:
            return Response({"error": "No resume available"}, status=400)

        system = data.get("system") or ""
        messages = data.get("messages") or []
        tools = data.get("tools") or {}
        cursor = data.get("cursor")
        selection = data.get("selection")

        generator = self._run(request, messages, system, tools, resume, cursor, selection)
        response = StreamingHttpResponse(generator, content_type="text/event-stream")
        response["X-Vercel-AI-UI-Message-Stream"] = "v1"
        response["Cache-Control"] = "no-cache"
        response["Connection"] = "keep-alive"
        return response

    async def _run(self, request, messages, system, tools, resume, cursor, selection):
        openai_messages = _to_ui_messages(messages, system, resume)
        steps = 0

        while True:
            meta = None
            async for chunk in deepseek.stream_chat(
                openai_messages,
                tools,
                settings.DEEPSEEK_API_URL,
                settings.DEEPSEEK_MODEL,
                settings.DEEPSEEK_API_KEY,
            ):
                if "tool_calls" in chunk:
                    meta = chunk
                    continue
                yield self._sse(chunk)

            if meta is None:
                yield self._sse({"type": "finish", "finishReason": "stop"})
                return

            finish_reason = meta.get("finish_reason")
            tool_calls = meta.get("tool_calls") or []

            if finish_reason == "error":
                yield self._sse({"type": "error", "errorText": meta.get("error", "DeepSeek error")})
                return

            if not tool_calls or steps >= MAX_STEPS:
                yield self._sse({"type": "finish", "finishReason": "stop"})
                return

            # Build the assistant message with tool_calls, then execute each tool.
            assistant_message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["input"])},
                    }
                    for tc in tool_calls
                ],
            }
            openai_messages.append(assistant_message)

            for tc in tool_calls:
                name = tc["name"]
                executor = TOOL_EXECUTORS.get(name)
                if executor is None:
                    result = {"success": False, "error": f"Unknown tool: {name}"}
                else:
                    try:
                        result = self._execute(name, resume, tc["input"], cursor, selection)
                    except Exception as exc:  # noqa: BLE001
                        result = {"success": False, "error": str(exc)}
                openai_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    },
                )

            steps += 1

    @staticmethod
    def _execute(name, resume, args, cursor, selection):
        if name == "insert_latex":
            return TOOL_EXECUTORS["insert_latex"](resume, args, cursor)
        if name == "replace_selection":
            return TOOL_EXECUTORS["replace_selection"](resume, args, cursor, selection)
        return TOOL_EXECUTORS[name](resume, args)

    @staticmethod
    def _sse(chunk: dict) -> str:
        return f"data: {json.dumps(chunk)}\n\n"
