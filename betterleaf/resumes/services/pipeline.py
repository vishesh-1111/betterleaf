"""Run a resume PDF through the whole pipeline without touching the database.

PDF -> text -> structured data -> LaTeX -> compiled PDF. Uses the same
functions the upload and compile views use.
"""

import pymupdf

from betterleaf.resumes.services.compiler import compile_latex
from betterleaf.resumes.services.fit import fit_resume
from betterleaf.resumes.services.extract import pdf_to_text
from betterleaf.resumes.services.latex import render_resume
from betterleaf.resumes.services.parser import extract_resume


class PipelineError(Exception):
    """The compiler produced no PDF."""


def count_pages(pdf_bytes: bytes) -> int:
    """Return the number of pages in a PDF."""
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


def resume_pdf_to_pdf(pdf_bytes: bytes) -> bytes:
    """Take an uploaded resume PDF and return the final compiled PDF."""
    data = extract_resume(pdf_to_text(pdf_bytes))
    result = fit_resume(data)
    if not result.pdf:
        status, log, pdf = compile_latex(render_resume(data))
        if not pdf:
            msg = f"No PDF produced (exit {status}): {log[-500:]}"
            raise PipelineError(msg)
        return pdf
    return result.pdf
