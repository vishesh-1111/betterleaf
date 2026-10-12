"""Bare-minimum LaTeX compile microservice.

Stdlib-only HTTP server that accepts a set of source files, runs a single
`pdflatex` pass, and returns the PDF bytes (base64) plus the compile log.

Wire shape (matches TeXlyre `CompileResult` conventions):

    POST /compile
    {"mainFile": "main.tex",
     "files": [{"path": "main.tex", "content": "<base64 utf-8>"}]}
    -> {"status": 0, "log": "...", "pdf": "<base64 or null>"}

Single pass only: no bibtex, no makeindex, no rerun. Cross-references and
bibliographies will NOT converge; that is an intentional boundary.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = 7030  # matches TeXlyre's ws://localhost:7030 placeholder
COMPILE_TIMEOUT = 120
MAX_BODY_BYTES = 32 * 1024 * 1024  # guard against unbounded request bodies

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

logger = logging.getLogger("latex-server")


class CompileError(Exception):
    """A client-side (400) problem with the compile request."""


def _decode_main_file(payload: dict) -> str:
    main_file = payload.get("mainFile")
    if not isinstance(main_file, str) or not main_file:
        raise CompileError("mainFile must be a non-empty string")
    # TeXlyre sends the full project path (e.g. "chapters/main.tex"); we only
    # ever write files into a flat tempdir, so normalize to the basename.
    main_file = Path(main_file).name
    if not main_file.endswith(".tex"):
        raise CompileError("mainFile must end in .tex")
    return main_file


def _decode_files(payload: dict) -> list[tuple[str, bytes]]:
    files = payload.get("files")
    if not isinstance(files, list):
        raise CompileError("files must be a list")
    decoded: list[tuple[str, bytes]] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise CompileError("each files[] entry must be an object")
        path = entry.get("path")
        content = entry.get("content")
        if not isinstance(path, str) or not path:
            raise CompileError("files[].path must be a non-empty string")
        if not isinstance(content, str):
            raise CompileError("files[].content must be a base64 string")
        try:
            raw = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CompileError(f"files[{path}].content is not valid base64: {exc}") from exc
        decoded.append((Path(path).name, raw))
    return decoded


def compile_document(main_file: str, files: list[tuple[str, bytes]]) -> dict:
    """Run one pdflatex pass. Never raises for TeX failures; returns the result."""
    tmpdir = Path(tempfile.mkdtemp(prefix="texlyre-compile-"))
    try:
        for name, raw in files:
            (tmpdir / name).write_bytes(raw)

        try:
            proc = subprocess.run(  # noqa: S603 - pinned trusted binary, no shell
                [  # noqa: S607
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    main_file,
                ],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": -1,
                "log": f"Compilation timed out after {COMPILE_TIMEOUT}s.",
                "pdf": None,
            }

        log = (proc.stdout or "") + (proc.stderr or "")
        pdf_path = tmpdir / f"{Path(main_file).stem}.pdf"
        pdf_b64 = None
        if pdf_path.exists():
            pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        return {"status": proc.returncode, "log": log, "pdf": pdf_b64}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "texlyre-latex-server"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        for key, value in CORS_HEADERS.items():
            self.send_header(key, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_OPTIONS(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/compile":
            self._send(404, b"", "text/plain; charset=utf-8")
            return
        self._send(204, b"", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/compile":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send_json(400, {"error": "invalid Content-Length"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "missing or oversized request body"})
            return

        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "request body must be a JSON object"})
            return

        try:
            main_file = _decode_main_file(payload)
            files = _decode_files(payload)
        except CompileError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        result = compile_document(main_file, files)
        self._send_json(200, result)

    def log_message(self, fmt: str, *args) -> None:
        logger.info("%s %s -> %s", self.command, self.path, args[1] if len(args) > 1 else args)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info("latex compile service listening on %s:%s", HOST, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
