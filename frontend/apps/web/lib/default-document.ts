export const DEFAULT_TEX_CONTENT = `\\documentclass[11pt]{article}
\\usepackage[margin=1in]{geometry}
\\usepackage{amsmath}
\\usepackage{graphicx}
\\usepackage{tikz-cd}
\\usepackage{multicol}

\\setlength{\\parindent}{0pt}
\\setlength{\\parskip}{1\\baselineskip}

\\begin{document}

\\section*{What is Open-Prism?}

\\textbf{Open-Prism} is an AI-powered \\LaTeX{} editor for writing scientific documents. It features built-in AI assistance to help you draft and edit text, reason through ideas, and handle formatting.

\\section*{Features}

\\begin{multicols}{2}
Open-Prism integrates AI directly in the editor with access to your project, so you can ask it to:

\`\`Add the Laplace transform of $t\\cos(at)$ in the introduction.''
\\[
  \\mathcal{L}\\left\\{ t \\cos(a t) \\right\\} = \\frac{ s^2 - a^2 }{ (s^2 + a^2)^2 }
\\]

\`\`Add a 4\\,$\\times$\\,4 table in the results section.''
\\begin{center}
\\resizebox{0.5\\linewidth}{!}{%
\\begin{tabular}{|c|c|c|c|}
  \\hline
  1 & 2 & 3 & 4 \\\\
  \\hline
  5 & 6 & 7 & 8 \\\\
  \\hline
  9 & 10 & 11 & 12 \\\\
  \\hline
  13 & 14 & 15 & 16 \\\\
  \\hline
\\end{tabular}%
}
\\end{center}

\`\`Please proofread this section, flag any errors or logical gaps, and suggest improvements for clarity.''

\`\`Am I missing corollaries or implications of Theorem 3.1? Are all bounds tight, or can some be relaxed?''

\\columnbreak

\`\`Write an abstract based on the rest of the paper.''

\`\`Add references to my paper and suggest related work I may have missed.''

\`\`Convert this hand-drawn diagram to \\LaTeX{}.''
\\par\\noindent
\\begin{minipage}[t]{0.49\\linewidth}
  \\vspace{0pt}
  \\centering
  \\includegraphics[width=\\linewidth]{hand-write.jpg}
\\end{minipage}\\hfill
\\begin{minipage}[t]{0.49\\linewidth}
  \\vspace{0pt}
  \\centering
  \\resizebox{\\linewidth}{!}{$
    \\begin{tikzcd}[row sep=2em, column sep=1.5em, ampersand replacement=\\&]
      E
        \\arrow[dr, "e"']
        \\arrow[drr, "p_2"]
        \\arrow[ddr, "p_1"']
      \\& \\& \\\\
      \\& A \\times B \\arrow[r, "\\pi_2"'] \\arrow[d, "\\pi_1"] \\& B \\arrow[d, "g"] \\\\
      \\& A \\arrow[r, "f"'] \\& C
    \\end{tikzcd}
  $}
\\end{minipage}
\\par

\`\`Fill in all missing dependencies in my project.''

\`\`Generate a 200-word summary for a general audience.''

\`\`Create a Beamer presentation with each slide in a separate file.''
\\end{multicols}

\\section*{Getting Started}

Press \\textbf{Enter} to compile your document. Use \\textbf{Shift+Enter} for a new line. The AI assistant panel at the bottom of the editor is ready to help with any \\LaTeX{} questions or tasks.

\\end{document}
`;
