"""Fit a resume to its page limit by adjusting only spacing and size.

Content is never changed or removed. A single ``tightness`` value
(0 = loosest, 1 = tightest) drives every layout knob (see
:func:`latex.layout_for`); we binary-search it for the loosest setting that
still fits the page limit with a little room to spare.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

import pymupdf

from betterleaf.resumes.services.compiler import compile_latex
from betterleaf.resumes.services.latex import layout_for
from betterleaf.resumes.services.latex import render_resume

MAX_TRIES = 6
MIN_ROOM = 0.015  # keep at least this share of the page free (a little room)
MAX_EMPTY = 0.06  # more free space than this share of the page => go looser


@dataclass
class Measurement:
    pages: int
    free_fraction: float  # empty share of the last page's text area (0..1)


@dataclass
class Suggestion:
    action: str  # "shorten_new" | "shorten_other" | "replace_other"
    bullet_id: str
    text: str
    reason: str


@dataclass
class FitResult:
    fits: bool
    tightness: float
    latex: str
    pdf: bytes | None
    measurement: Measurement | None
    tries: int
    suggestions: list[Suggestion] = field(default_factory=list)


def measure_pdf(pdf: bytes, tightness: float) -> Measurement:
    """Return page count and how much of the last page's text area is empty."""
    layout = layout_for(tightness)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        last = doc[doc.page_count - 1]
        top = layout.vert_in * 72
        bottom = last.rect.height - layout.vert_in * 72
        ys = [b[3] for b in last.get_text("blocks") if b[3] <= last.rect.height]
        lowest = max(ys, default=top)
        free = max(0.0, (bottom - lowest) / (bottom - top))
        return Measurement(doc.page_count, min(1.0, free))


def _compile(data, tightness: float) -> tuple[str, bytes | None, Measurement | None]:
    latex = render_resume(data, tightness)
    _, _, pdf = compile_latex(latex)
    return latex, pdf, (measure_pdf(pdf, tightness) if pdf else None)


def fit_resume(data, page_limit: int = 1) -> FitResult:
    """Find the loosest tightness that fits ``page_limit`` pages."""
    lo, hi = 0.0, 1.0
    best: FitResult | None = None
    last: FitResult | None = None
    tries = 0

    def attempt(t: float) -> tuple[FitResult | None, str]:
        nonlocal tries, last
        tries += 1
        latex, pdf, m = _compile(data, t)
        if m is None:
            return None, "error"
        res = FitResult(True, t, latex, pdf, m, tries)
        last = res
        if m.pages > page_limit or (m.pages == page_limit and m.free_fraction < MIN_ROOM):
            return res, "tighter"
        if m.pages < page_limit or m.free_fraction > MAX_EMPTY:
            return res, "looser"
        return res, "ok"

    for _ in range(MAX_TRIES):
        mid = (lo + hi) / 2
        res, verdict = attempt(mid)
        if verdict == "error":
            break
        if verdict == "ok":
            res.tries = tries
            return res
        if verdict == "tighter":
            lo = mid
        else:
            hi = mid
            best = res  # fits, but looser could still work; keep loosest-so-far

    if best is not None:
        best.tries = tries
        return best

    res, verdict = attempt(1.0)  # does it fit at all?
    if res is not None and verdict != "tighter":
        res.tries = tries
        return res
    return FitResult(
        False, 1.0, res.latex if res else render_resume(data, 1.0),
        res.pdf if res else None, res.measurement if res else None, tries,
    )


def _all_bullets(data: dict) -> list[tuple[str, dict]]:
    out = []
    for key in ("experience", "projects", "achievements"):
        for item in data.get(key) or []:
            for b in item.get("bullets") or []:
                out.append((key, b))
    return out


def suggest_trims(
    data: dict, new_bullet_id: str | None = None,
    relevance: dict[str, float] | None = None,
) -> list[Suggestion]:
    """Options for the user when content can't fit. Nothing is changed."""
    bullets = _all_bullets(data)
    out: list[Suggestion] = []
    for _, b in bullets:
        if b["id"] == new_bullet_id:
            out.append(Suggestion(
                "shorten_new", b["id"], b["text"],
                "Shorten the bullet you just added.",
            ))
    others = [b for _, b in bullets if b["id"] != new_bullet_id]
    for b in sorted(others, key=lambda b: len(b["text"]), reverse=True)[:3]:
        out.append(Suggestion(
            "shorten_other", b["id"], b["text"], "One of your longest bullets.",
        ))
    if relevance:
        ranked = sorted(others, key=lambda b: relevance.get(b["id"], 1.0))[:3]
    else:
        ranked = []
    for b in ranked:
        out.append(Suggestion(
            "replace_other", b["id"], b["text"], "Least relevant to this job.",
        ))
    return out


def check_bullet_fit(
    data: dict, new_bullet_id: str | None = None, page_limit: int = 1,
    relevance: dict[str, float] | None = None,
) -> FitResult:
    """Fit ``data`` (already containing the new bullet); on failure return
    suggestions instead of removing anything."""
    result = fit_resume(data, page_limit)
    if not result.fits:
        result.suggestions = suggest_trims(data, new_bullet_id, relevance)
    return result
