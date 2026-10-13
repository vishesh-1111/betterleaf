import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.chat import deepseek
from betterleaf.chat.serializers import ChatRequestSerializer
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Resume

TECTONIC_TIMEOUT = 30

_FENCE_RE = re.compile(r"```(?:latex|tex)?\s*\n(.*?)```", re.DOTALL)


def _extract_latex(text: str) -> str | None:
    """Pull the full LaTeX document out of the assistant's fenced code block.

    Falls back to the raw text when no fence is present (in case the model
    returned a bare document without a code block).
    """
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("\\") or "%" in stripped[:64]:
        return stripped
    return None


def _compile(resume: Resume, latex: str) -> tuple[bool, str]:
    """Synchronously compile ``latex`` with tectonic.

    Returns ``(success, log)``. Mirrors ``resumes.tasks.compile_resume`` but runs
    inline so the chat view can decide whether to persist the new source.
    """
    template = TEMPLATE_CATALOG[resume.template]
    tmpdir = Path(tempfile.mkdtemp(prefix="betterleaf-chat-compile-"))
    try:
        (tmpdir / "main.tex").write_text(latex)
        if template.cls_path is not None:
            shutil.copy(template.cls_path, tmpdir / "resume.cls")
        proc = subprocess.run(  # noqa: S603 — pinned trusted binary, no shell
            ["tectonic", "--outdir", str(tmpdir), "main.tex"],  # noqa: S607
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=TECTONIC_TIMEOUT,
            check=False,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
        pdf_path = tmpdir / "main.pdf"
        return (proc.returncode == 0 and pdf_path.exists()), log
    except subprocess.TimeoutExpired:
        return False, f"Compilation timed out after {TECTONIC_TIMEOUT}s."
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


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

        generator = self._run(messages, system, resume)
        response = StreamingHttpResponse(generator, content_type="text/event-stream")
        response["X-Vercel-AI-UI-Message-Stream"] = "v1"
        response["Cache-Control"] = "no-cache"
        response["Connection"] = "keep-alive"
        return response

    async def _run(self, messages, system, resume):
        openai_messages = _to_ui_messages(messages, system, resume)

        meta = None
        async for chunk in deepseek.stream_chat(
            openai_messages,
            settings.DEEPSEEK_API_URL,
            settings.DEEPSEEK_MODEL,
            settings.DEEPSEEK_API_KEY,
        ):
            if "full_text" in chunk:
                meta = chunk
                continue
            yield self._sse(chunk)

        if meta is None:
            yield self._sse({"type": "finish", "finishReason": "stop"})
            return

        if meta.get("finish_reason") == "error":
            yield self._sse({"type": "error", "errorText": meta.get("error", "DeepSeek error")})
            return

        latex = _extract_latex(meta.get("full_text") or "")
        if latex is None:
            yield self._sse({"type": "error", "errorText": "No LaTeX document found in the response."})
            return

        success, log = await self._compile_async(resume, latex)
        if success:
            resume.main_tex = latex
            resume.save(update_fields=["main_tex", "updated_at"])
        else:
            yield self._sse(
                {
                    "type": "error",
                    "errorText": f"Compilation failed:\n{log[-2000:]}",
                },
            )
            return

        yield self._sse({"type": "finish", "finishReason": "stop"})

    @staticmethod
    async def _compile_async(resume, latex):
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _compile, resume, latex)

    @staticmethod
    def _sse(chunk: dict) -> str:
        return f"data: {json.dumps(chunk)}\n\n"
