"""Deterministic LaTeX generation for Jake's Resume template.

Turns a validated :class:`ResumeData` (its ``model_dump()`` JSON is pydantic-
friendly) into a complete, self-contained LaTeX document targeting the Jake's
template starter (``template_src/jakes/starter.tex``). The output is usable as
the ``main_tex`` of a :class:`betterleaf.resumes.models.Resume`.

Determinism guarantees:
- Section order is fixed (Education, Experience, Projects, Technical Skills,
  Achievements) regardless of the order keys appear in the input JSON.
- Any subset of optional contact fields renders in a stable order.
- Every user string is LaTeX-escaped, so ``&``, ``%``, ``_``, ``#``, etc. in
  resume content cannot break compilation.
- Empty sections are omitted entirely.
"""

from betterleaf.resumes.services.schemas import ResumeData

# Fixed, canonical section order. Input JSON may list keys in any order; the
# generator always renders sections in this sequence and skips empty ones.
_SECTION_ORDER = (
    "education",
    "experience",
    "projects",
    "technical_skills",
    "achievements",
)

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


# --- Section renderers -----------------------------------------------------


def _render_heading(data: ResumeData) -> str:
    """Name and contact line; contact fields are all optional."""
    contact = data.contact
    parts: list[str] = []
    if contact.phone:
        parts.append(contact.phone)
    if contact.email:
        parts.append(
            rf"\href{{mailto:{_escape(contact.email)}}}{{\underline{{{_escape(contact.email)}}}}}"
        )
    if contact.linkedin:
        parts.append(
            rf"\href{{https://{_escape(contact.linkedin)}}}{{\underline{{{_escape(contact.linkedin)}}}}}"
        )
    if contact.github:
        parts.append(
            rf"\href{{https://{_escape(contact.github)}}}{{\underline{{{_escape(contact.github)}}}}}"
        )
    if contact.portfolio:
        parts.append(
            rf"\href{{https://{_escape(contact.portfolio)}}}{{\underline{{{_escape(contact.portfolio)}}}}}"
        )

    inner = [rf"\textbf{{\Huge \scshape {_escape(data.name)}}}"]
    if parts:
        inner[0] += r" \\ \vspace{1pt}"
        inner.append(r"\small " + r" $|$ ".join(parts))
    return (
        "\\begin{center}\n    "
        + "\n    ".join(inner)
        + "\n\\end{center}"
    )


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
                    f"        \\resumeItemPlain{{{_escape(bullet)}}}"
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
            links.append(
                rf"\href{{https://{_escape(proj['github'])}}}{{\underline{{GitHub}}}}"
            )
        if proj.get("deployed"):
            links.append(
                rf"\href{{https://{_escape(proj['deployed'])}}}{{\underline{{Live}}}}"
            )
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
                    f"            \\resumeItemPlain{{{_escape(bullet)}}}"
                )
            lines.append("          \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _render_skills(items: list) -> str:
    lines = ["\\section{Technical Skills}\n  \\resumeSubHeadingListStart"]
    skills = [
        rf"\textbf{{{_escape(skill['key'])}}}: {_escape(skill['value'])}"
        for skill in items
        if skill.get("key") or skill.get("value")
    ]
    if skills:
        lines.append("    \\item{\n      " + "\n      \\hfill\n      ".join(skills) + "\n    }")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


def _render_achievements(items: list) -> str:
    lines = ["\\section{Achievements}\n  \\resumeSubHeadingListStart"]
    for ach in items:
        lines.append(
            "    \\resumeSubheading\n"
            f"      {{{_escape(ach['title'])}}}{{}}\n"
            f"      {{}}{{}}"
        )
        bullets = ach.get("bullets") or []
        if bullets:
            lines.append("      \\resumeItemListStart")
            for bullet in bullets:
                lines.append(
                    f"        \\resumeItemPlain{{{_escape(bullet)}}}"
                )
            lines.append("      \\resumeItemListEnd")
    lines.append("  \\resumeSubHeadingListEnd")
    return "\n".join(lines)


_SECTION_RENDERERS = {
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
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
%%%%%%  RESUME STARTS HERE  %%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""


def _render_sections(data: ResumeData) -> str:
    """Render non-empty sections in the fixed canonical order."""
    dumped = data.model_dump()
    sections: list[str] = []
    for key in _SECTION_ORDER:
        items = dumped.get(key) or []
        if not items:
            continue
        sections.append(_SECTION_RENDERERS[key](items))
    return "\n\n\n".join(sections)


def render_resume(data: ResumeData | dict | str | bytes) -> str:
    """Render a deterministic Jake's-template LaTeX document from resume data.

    Accepts a validated :class:`ResumeData`, a dict, a JSON string, or JSON
    bytes. Returns the complete LaTeX source.
    """
    if isinstance(data, ResumeData):
        model = data
    elif isinstance(data, bytes):
        model = ResumeData.model_validate_json(data)
    elif isinstance(data, str):
        model = ResumeData.model_validate_json(data)
    else:
        model = ResumeData.model_validate(data)

    heading = _render_heading(model)
    body = _render_sections(model)
    parts = [_PREAMBLE, "\\begin{document}", "", heading]
    if body:
        parts.append(body)
    parts.append("")
    parts.append("\\end{document}")
    return "\n".join(parts)
