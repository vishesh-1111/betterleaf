/** Split a raw LaTeX line into styled spans (commands + braces).
 * The `.cmd` / `.br` colours live in styles/landing.css. */
export function LaTeXLine({ text }: { text: string }) {
  if (text.startsWith("%")) {
    return <span className="br">{text}</span>;
  }
  const parts = text.split(/(\\[a-zA-Z]+|[{}])/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("\\"))
          return (
            <span key={i} className="cmd">
              {part}
            </span>
          );
        if (part === "{" || part === "}")
          return (
            <span key={i} className="br">
              {part}
            </span>
          );
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
