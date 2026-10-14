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


def _join(items: list[str], sep: str) -> str:
    return sep.join(item for item in items if item)


def _bullet_text(bullet) -> str:
    """Extract the plain-text content of a bullet.

    Bullets are stored as ``{"id": ..., "text": ...}`` dicts (see
    :class:`betterleaf.resumes.services.schemas.Bullet`). Accept a dict for
    the validated path and fall back to a bare string for inputs that reached
    us pre-validation.
    """
    if isinstance(bullet, dict):
        return bullet.get("text") or ""
    return bullet or ""


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
    or raw URL text): GitHub shows the bare username, LinkedIn and Portfolio
    show fixed labels.
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
        parts.append(_link(url, contact.github.strip()))
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
    return f"\\section{{Summary}}\n  {_escape(text)}"


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
                    f"        \\resumeItemPlain{{{_escape(_bullet_text(bullet))}}}"
                )
            lines.append("      \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _render_projects(items: list) -> str:
    lines = ["\\section{Projects}\n  \\resumeSubHeadingListStart"]
    for proj in items:
        title = _escape(proj["title"])
        tech_stack = proj.get("tech_stack") or ""
        header = rf"\resumeProjectHeading{{\textbf{{{title}}}"
        if tech_stack:
            header += rf" \enspace|\enspace \emph{{{_escape(tech_stack)}}}"
        header += r"}{}"
        lines.append(f"    {header}")

        links: list[str] = []
        if proj.get("github"):
            url = _normalize_https(proj["github"], "https://github.com/")
            links.append(rf"\href{{{_escape(url)}}}{{\underline{{GitHub}}}}")
        if proj.get("deployed"):
            url = _normalize_https(proj["deployed"], "https://")
            links.append(rf"\href{{{_escape(url)}}}{{\underline{{Live}}}}")
        if links:
            lines.append(
                "          \\resumeItemListStart\n"
                f"            \\resumeItemPlain{{{ ' $|$ '.join(links) }}}\n"
                "          \\resumeItemListEnd"
            )

        bullets = proj.get("bullets") or []
        if bullets:
            lines.append("          \\resumeItemListStart")
            for bullet in bullets:
                lines.append(
                    f"            \\resumeItemPlain{{{_escape(_bullet_text(bullet))}}}"
                )
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
                    f"        \\resumeItemPlain{{{_escape(_bullet_text(bullet))}}}"
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

_PREAMBLE = r"""%-------------------------
% Generated by BetterLeaf — Jake's Resume template
%-------------------------

\documentclass[letterpaper,11pt]{article}

\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}

\pagestyle{fancy}
\fancyhf{} % Clear all header and footer fields
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% Adjust margins
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}

\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% Sections formatting
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
    \end{tabular*}\vspace{-7pt}
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
\newcommand{\resumeItemListStart}{\begin{itemize}[itemsep=0pt, topsep=0pt, parsep=0pt, partopsep=0pt]}
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


def render_resume(data: ResumeData | dict | str | bytes) -> str:
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
    parts = [_PREAMBLE, "\\begin{document}", "", heading]
    if body:
        parts.append(body)
    parts.append("")
    parts.append("\\end{document}")
    return "\n".join(parts)
