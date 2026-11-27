"""Deterministic LaTeX generation for Jake's Resume template.

Turns a validated :class:`ResumeData` (its ``model_dump()`` JSON is pydantic-
friendly) into a complete, self-contained LaTeX document targeting the Jake's
template starter (``template_src/jakes/starter.tex``). The output is usable as
the ``main_tex`` of a :class:`betterleaf.resumes.models.Resume`.

Determinism guarantees:
- Section order is dynamic: it follows ``section_order`` (inferred from the
  input JSON's key order) when available, with a fixed fallback for any
  remaining sections.
- Any subset of optional contact fields renders in a stable order.
- Every user string is LaTeX-escaped, so ``&``, ``%``, ``_``, ``#``, etc. in
  resume content cannot break compilation.
- Empty sections are omitted entirely.
"""

import json
import re
from dataclasses import dataclass

from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.schemas import SECTION_KEYS

# Fallback section order, used only when the input carries no explicit
# ``section_order``. Sections present in neither ``section_order`` nor this
# fallback still render (appended in ``SECTION_KEYS`` order).
_FALLBACK_ORDER = SECTION_KEYS

_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape(text: str) -> str:
    """Escape LaTeX special characters in a plain-text string."""
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


def _escape_rich(text: str) -> str:
    """Escape ``text``, turning Markdown ``**bold**`` spans into ``\\textbf{}``.

    Unbalanced ``**`` markers are dropped rather than left to break bolding.
    """
    parts = text.split("**")
    if len(parts) % 2 == 0:
        return _escape(text.replace("**", ""))
    return "".join(
        rf"\textbf{{{_escape(part)}}}" if i % 2 and part else _escape(part)
        for i, part in enumerate(parts)
    )


def _join(items: list[str], sep: str) -> str:
    return sep.join(item for item in items if item)


# --- Section renderers -----------------------------------------------------


def _normalize_https(value: str, prefix: str) -> str:
    """Return ``value`` as an absolute URL, prepending ``prefix`` when it is
    a bare handle/username rather than an already-absolute URL."""
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    return f"{prefix}{value}"


def _link(url: str, label: str) -> str:
    """Render a clickable word: ``label`` links to ``url``, no URL shown."""
    return rf"\href{{{_escape(url)}}}{{\underline{{{_escape(label)}}}}}"


def _render_heading(data: ResumeData) -> str:
    """Name and contact line; contact fields are all optional.

    Each URL-backed field renders as a short clickable word (no ``https://``
    or raw URL text): GitHub, LinkedIn and Portfolio show fixed labels.
    """
    contact = data.contact
    parts: list[str] = []
    if contact.phone:
        parts.append(_escape(contact.phone))
    if contact.email:
        parts.append(
            rf"\href{{mailto:{_escape(contact.email)}}}{{\underline{{{_escape(contact.email)}}}}}"
        )
    if contact.linkedin:
        url = _normalize_https(contact.linkedin, "https://linkedin.com/in/")
        parts.append(_link(url, "LinkedIn"))
    if contact.github:
        url = _normalize_https(contact.github, "https://github.com/")
        parts.append(_link(url, "GitHub"))
    if contact.portfolio:
        url = _normalize_https(contact.portfolio, "https://")
        parts.append(_link(url, "Portfolio"))

    inner = [rf"\textbf{{\Huge \scshape {_escape(data.name)}}}"]
    if parts:
        inner[0] += r" \\ \vspace{1pt}"
        inner.append(r"\small " + r" $|$ ".join(parts))
    return (
        "\\begin{center}\n    "
        + "\n    ".join(inner)
        + "\n\\end{center}"
    )


def _render_summary(value: dict | None) -> str:
    text = (value or {}).get("text") or ""
    return f"\\section{{Summary}}\n  {_escape_rich(text)}"


def _render_education(items: list) -> str:
    lines = [
        "\\section{Education}\n  \\resumeSubHeadingListStart"
    ]
    for edu in items:
        lines.append(
            "    \\resumeSubheading\n"
            f"      {{{_escape(edu['institution'])}}}{{}}\n"
            f"      {{{_escape(edu['degree'])}}}{{{_escape(edu['duration'])}}}"
        )
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _render_experience(items: list) -> str:
    lines = [
        "\\section{Experience}\n  \\resumeSubHeadingListStart"
    ]
    for exp in items:
        lines.append(
            "    \\resumeSubheading\n"
            f"      {{{_escape(exp['company'])}}}{{}}\n"
            f"      {{{_escape(exp['role'])}}}{{{_escape(exp['duration'])}}}"
        )
        bullets = exp.get("bullets") or []
        if bullets:
            lines.append("      \\resumeItemListStart")
            for bullet in bullets:
                lines.append(
                    f"        \\resumeItemPlain{{{_escape_rich(bullet['text'])}}}"
                )
            lines.append("      \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


# A parsed bullet like "Source Code: GitHub Repository" duplicates the link line
# we append ourselves, so it is dropped when the project has a github link.
_SOURCE_BULLET_RE = re.compile(r"\s*\W*\s*source\s*code\b", re.IGNORECASE)


def _render_projects(items: list) -> str:
    lines = ["\\section{Projects}\n  \\resumeSubHeadingListStart"]
    for proj in items:
        title = _escape(proj["title"])
        if proj.get("deployed"):
            url = _normalize_https(proj["deployed"], "https://")
            title = rf"\href{{{_escape(url)}}}{{\underline{{{title}}}}}"
        tech_stack = _escape(proj.get("tech_stack") or "")
        right = rf"\textit{{\small {tech_stack}}}" if tech_stack else ""
        lines.append(
            f"    \\resumeProjectHeading{{\\textbf{{{title}}}}}{{{right}}}"
        )

        bullets = [
            _escape_rich(b["text"])
            for b in proj.get("bullets") or []
            if not (proj.get("github") and _SOURCE_BULLET_RE.match(b["text"]))
        ]
        if proj.get("github"):
            url = _normalize_https(proj["github"], "https://github.com/")
            bullets.append(
                rf"\href{{{_escape(url)}}}{{\underline{{GitHub}}}}"
            )
        if bullets:
            lines.append("          \\resumeItemListStart")
            lines.extend(f"            \\resumeItemPlain{{{b}}}" for b in bullets)
            lines.append("          \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _render_skills(items: list) -> str:
    rows = [
        rf"\textbf{{{_escape(skill['key'])}}}: {_escape(skill['value'])}"
        for skill in items
        if skill.get("key") or skill.get("value")
    ]
    body = " \\\\\n      ".join(rows)
    lines = [
        "\\section{Technical Skills}",
        "  \\begin{itemize}[leftmargin=0.15in, label={}]",
        "    \\small{\\item{",
        "      " + body,
        "    }}",
        "  \\end{itemize}",
    ]
    return "\n".join(lines)


def _render_achievements(items: list) -> str:
    lines = ["\\section{Achievements}\n  \\resumeSubHeadingListStart"]
    for ach in items:
        lines.append(
            rf"    \item\textbf{{{_escape(ach['title'])}}}"
        )
        bullets = ach.get("bullets") or []
        if bullets:
            lines.append("      \\resumeItemListStart")
            for bullet in bullets:
                lines.append(
                    f"        \\resumeItemPlain{{{_escape_rich(bullet['text'])}}}"
                )
            lines.append("      \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


_SECTION_RENDERERS = {
    "summary": _render_summary,
    "education": _render_education,
    "experience": _render_experience,
    "projects": _render_projects,
    "technical_skills": _render_skills,
    "achievements": _render_achievements,
}

@dataclass(frozen=True)
class Layout:
    """Concrete look of the page, derived from one tightness value."""

    font_pt: float
    leading_pt: float
    side_in: float
    vert_in: float
    item_gap_pt: float
    section_gap_pt: float
    rule_gap_pt: float


# (loosest, tightest) bounds for every adjustable value.
_FONT = (11.0, 9.0)
_LEADING_RATIO = (1.25, 1.12)
_SIDE_IN = (0.7, 0.4)
_VERT_IN = (0.65, 0.35)
_ITEM_GAP = (7.0, 1.0)
_SECTION_GAP = (12.0, 2.0)
# Space under the section rule. The template pulls content up 5pt after the
# rule, so this must stay above 5pt or the rule cuts through the bullets.
_RULE_GAP = (10.0, 7.0)

DEFAULT_TIGHTNESS = 0.25


def layout_for(tightness: float) -> Layout:
    """Map tightness (0 = loosest, 1 = tightest) to a :class:`Layout`."""
    t = min(1.0, max(0.0, tightness))

    def lerp(bounds: tuple[float, float]) -> float:
        return bounds[0] + (bounds[1] - bounds[0]) * t

    font = lerp(_FONT)
    return Layout(
        font_pt=round(font, 2),
        leading_pt=round(font * lerp(_LEADING_RATIO), 2),
        side_in=round(lerp(_SIDE_IN), 3),
        vert_in=round(lerp(_VERT_IN), 3),
        item_gap_pt=round(lerp(_ITEM_GAP), 2),
        section_gap_pt=round(lerp(_SECTION_GAP), 2),
        rule_gap_pt=round(lerp(_RULE_GAP), 2),
    )


_PREAMBLE = r"""%-------------------------
% Generated by BetterLeaf — Jake's Resume template
%-------------------------

\documentclass[letterpaper,11pt]{article}

\usepackage[letterpaper,left=%%SIDE%%in,right=%%SIDE%%in,top=%%VERT%%in,bottom=%%VERT%%in]{geometry}
\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[T1]{fontenc}
\usepackage{charter} % sturdier than Computer Modern, prints darker
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}

\pagestyle{fancy}
\fancyhf{} % Clear all header and footer fields
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Adjustable text size
\renewcommand{\normalsize}{\fontsize{%%FONT%%}{%%LEAD%%}\selectfont}
\renewcommand{\small}{\fontsize{%%SMALL%%}{%%SMALLLEAD%%}\selectfont}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
\titlespacing*{\section}{0pt}{%%SECGAP%%pt}{%%RULEGAP%%pt}
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

%-------------------------
% Custom commands
\newcommand{\resumeItem}[2]{
  \item\small{
    \textbf{#1}{: #2 \vspace{-2pt}}
  }
}

\newcommand{\resumeHeading}[4]{
    \begin{tabular*}{0.99\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small #3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-5pt}
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-1pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small #3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-5pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small #1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-5pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-3pt}
}

\newcommand{\resumeItemPlain}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubItem}[2]{\resumeItem{#1}{#2}\vspace{-4pt}}

\renewcommand{\labelitemii}{$\circ$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=*]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}[itemsep=%%ITEMGAP%%pt, topsep=0pt, parsep=0pt, partopsep=0pt]}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""


def _section_keys_in_order(data: ResumeData) -> list[str]:
    """Return section keys in render order, honoring ``section_order``.

    Non-empty sections follow ``data.section_order`` (explicit or LLM-inferred
    key order); any remaining non-empty sections are appended in the fallback
    ordering so no content is dropped.
    """
    dumped = data.model_dump()
    present = {k for k in SECTION_KEYS if dumped.get(k)}
    ordered = [k for k in data.section_order if k in present]
    ordered += [k for k in _FALLBACK_ORDER if k in present and k not in ordered]
    return ordered


def _render_sections(data: ResumeData) -> str:
    """Render non-empty sections in the order of ``data.section_order``."""
    dumped = data.model_dump()
    sections: list[str] = []
    for key in _section_keys_in_order(data):
        sections.append(_SECTION_RENDERERS[key](dumped[key]))
    return "\n\n\n".join(sections)


def _preamble(layout: Layout) -> str:
    values = {
        "SIDE": layout.side_in,
        "VERT": layout.vert_in,
        "FONT": layout.font_pt,
        "LEAD": layout.leading_pt,
        "SMALL": round(layout.font_pt - 1, 2),
        "SMALLLEAD": round(layout.leading_pt - 1, 2),
        "SECGAP": layout.section_gap_pt,
        "RULEGAP": layout.rule_gap_pt,
        "ITEMGAP": layout.item_gap_pt,
    }
    out = _PREAMBLE
    for key, val in values.items():
        out = out.replace(f"%%{key}%%", str(val))
    return out


def render_resume(
    data: ResumeData | dict | str | bytes,
    tightness: float = DEFAULT_TIGHTNESS,
) -> str:
    """Render a deterministic Jake's-template LaTeX document from resume data.

    Accepts a validated :class:`ResumeData`, a dict, a JSON string, or JSON
    bytes. Returns the complete LaTeX source.

    Section order follows ``ResumeData.section_order`` when present; otherwise
    it is inferred from the input's key order (a dict/JSON carries the LLM's
    section sequence) with a fixed fallback for any remaining sections.
    """
    if isinstance(data, ResumeData):
        model = data
    else:
        if isinstance(data, bytes):
            raw = json.loads(data)
        elif isinstance(data, str):
            raw = json.loads(data)
        else:
            raw = data or {}
        if not isinstance(raw, dict):
            model = ResumeData.model_validate(data)
        else:
            section_order = [k for k in raw if k in SECTION_KEYS and raw.get(k)]
            if section_order:
                raw = {**raw, "section_order": section_order}
            model = ResumeData.model_validate(raw)

    heading = _render_heading(model)
    body = _render_sections(model)
    parts = [_preamble(layout_for(tightness)), "\\begin{document}", "\\normalsize", heading]
    if body:
        parts.append(body)
    parts.append("")
    parts.append("\\end{document}")
    return "\n".join(parts)
