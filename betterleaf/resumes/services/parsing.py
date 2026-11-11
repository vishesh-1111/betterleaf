from betterleaf.resumes.services.extract import pdf_to_text
from betterleaf.resumes.services.parser import extract_resume


def parse_resume_upload(file_bytes: bytes, filename: str) -> dict:
    """
    Parse uploaded PDF into structured resume data.

    Args:
        file_bytes: PDF content as bytes
        filename: Original filename (for reference)

    Returns:
        Validated structured resume data (dict matching ResumeData schema)

    Raises:
        ValueError: If PDF cannot be extracted or parsed
    """
    try:
        markdown = pdf_to_text(file_bytes)
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}") from e

    try:
        resume_data = extract_resume(markdown)
        return resume_data.model_dump()
    except Exception as e:
        raise ValueError(f"Failed to parse resume content: {e}") from e
