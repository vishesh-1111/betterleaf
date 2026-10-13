import pymupdf
import pymupdf4llm


def pdf_to_text(data: bytes, password: str | None = None) -> str:
    """Extract LLM-ready Markdown from PDF bytes."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass and not doc.authenticate(password or ""):
            raise ValueError("PDF is encrypted; wrong or missing password.")
        return pymupdf4llm.to_markdown(doc, show_progress=False).strip()

