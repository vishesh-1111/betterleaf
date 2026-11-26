"""Eval: a one-page resume stays one page after the full pipeline.

Calls the real LLM and the real LaTeX service, so it only runs when asked:

    RUN_EVALS=1 pytest -n 3 betterleaf/resumes/evals/test_single_page.py
"""

import os
from pathlib import Path

import pytest

from betterleaf.resumes.services.pipeline import count_pages
from betterleaf.resumes.services.pipeline import resume_pdf_to_pdf

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_EVALS"),
    reason="set RUN_EVALS=1 to run (uses the real LLM and LaTeX service)",
)

REAL_RESUMES = Path(__file__).resolve().parents[3] / "Real_Resumes"


def _single_page_resumes() -> list[Path]:
    return [p for p in sorted(REAL_RESUMES.glob("*.pdf")) if count_pages(p.read_bytes()) == 1]


@pytest.mark.parametrize("path", _single_page_resumes(), ids=lambda p: p.stem)
def test_single_page_resume_stays_single_page(path: Path):
    final = resume_pdf_to_pdf(path.read_bytes())
    pages = count_pages(final)
    assert pages == 1, f"{path.name} became {pages} pages"
