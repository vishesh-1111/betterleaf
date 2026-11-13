"""LaTeX compilation via the texlive Docker microservice.

The texlive container (``compose/local/latex-server``) exposes a small HTTP
API; there is no local TeX installation inside the Django image. Every compile
is an HTTP call to ``POST /compile``.

Contract:

    Request   {"mainFile": "main.tex",
               "files": [{"path": "main.tex", "content": "<base64 utf-8>"}]}
    Response  {"status": <int exit code 0 = success>,
               "log": "...", "pdf": "<base64 | null>"}
"""

from __future__ import annotations

import base64

import httpx
from django.conf import settings

COMPILE_TIMEOUT = 120.0  # matches the latex-server's pdflatex ceiling


class LatexCompileError(Exception):
    """Raised when the compile service cannot be reached or misbehaves."""


def compile_latex(
    latex: str,
    *,
    extra_files: dict[str, bytes] | None = None,
    timeout: float = COMPILE_TIMEOUT,
) -> tuple[int, str, bytes | None]:
    """Compile ``latex`` and return ``(status, log, pdf_bytes)``.

    ``status`` is the compiler exit code (0 == success). ``pdf_bytes`` is
    ``None`` when compilation failed or no PDF was produced.

    ``extra_files`` maps filename -> raw bytes (e.g. ``resume.cls``) to send
    alongside ``main.tex``.

    Raises :class:`LatexCompileError` on transport/serialization failure so the
    caller can distinguish "could not compile" (status != 0) from "could not
    reach the compiler".
    """
    files = [
        {
            "path": "main.tex",
            "content": base64.b64encode(latex.encode("utf-8")).decode("ascii"),
        },
    ]
    for name, raw in (extra_files or {}).items():
        files.append(
            {
                "path": name,
                "content": base64.b64encode(raw).decode("ascii"),
            },
        )

    payload = {"mainFile": "main.tex", "files": files}
    try:
        response = httpx.post(
            settings.LATEX_API_URL + "/compile",
            json=payload,
            timeout=httpx.Timeout(timeout),
        )
    except httpx.HTTPError as exc:
        raise LatexCompileError(f"LaTeX service request failed: {exc}") from exc

    if response.status_code != 200:
        raise LatexCompileError(
            f"LaTeX service error {response.status_code}: {response.text[:500]}",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise LatexCompileError("LaTeX service returned non-JSON") from exc

    status = data.get("status")
    log = data.get("log") or ""
    pdf_b64 = data.get("pdf")
    try:
        pdf = base64.b64decode(pdf_b64, validate=True) if pdf_b64 else None
    except (ValueError, TypeError) as exc:
        raise LatexCompileError("LaTeX service returned a malformed PDF") from exc

    return status, log, pdf


def run_compilation(compilation) -> None:
    """Synchronously compile ``compilation.resume`` and persist the outcome.

    Imports are local to keep this module importable without Django models
    being loaded. Never raises for compile failures; they are recorded on the
    ``Compilation`` (status FAILED + log).
    """
    from django.utils import timezone

    from betterleaf.resumes.catalog import TEMPLATE_CATALOG
    from betterleaf.resumes.models import Compilation

    resume = compilation.resume
    compilation.status = Compilation.Status.RUNNING
    compilation.save(update_fields=["status"])

    def finish(status, log, pdf=None):
        if pdf:
            compilation.pdf_base64 = base64.b64encode(pdf).decode("ascii")
        compilation.status = status
        compilation.log = log
        compilation.finished_at = timezone.now()
        compilation.save()

    try:
        template = TEMPLATE_CATALOG[resume.template]
    except KeyError:
        finish(Compilation.Status.FAILED, f"Unknown template: {resume.template}")
        return

    extra_files: dict[str, bytes] = {}
    if template.cls_path is not None:
        extra_files["resume.cls"] = template.cls_path.read_bytes()

    try:
        status, log, pdf = compile_latex(resume.main_tex, extra_files=extra_files)
    except LatexCompileError as exc:
        finish(Compilation.Status.FAILED, str(exc))
        return

    if status == 0 and pdf:
        finish(Compilation.Status.SUCCEEDED, log, pdf)
    else:
        finish(Compilation.Status.FAILED, log)
