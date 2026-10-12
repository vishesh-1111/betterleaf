"""Canonical tool definitions and Django-side executors.

The three document-editing tools mirror the semantics that previously lived
client-side in ``frontend/.../latex-tools.tsx``. Each executor mutates
``Resume.main_tex`` and returns a result dict that is serialized back to
DeepSeek as the tool-call output.
"""

from betterleaf.resumes.models import Resume

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "insert_latex",
            "description": "Insert LaTeX code at the current cursor position in the document",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The LaTeX code to insert at the cursor position",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_selection",
            "description": "Replace the currently selected text in the document with LaTeX code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The LaTeX code to replace the selection with",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_and_replace",
            "description": "Find and replace text in the document. Use this to modify existing content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "find": {
                        "type": "string",
                        "description": "The exact text to find in the document",
                    },
                    "replace": {
                        "type": "string",
                        "description": "The text to replace it with",
                    },
                },
                "required": ["find", "replace"],
            },
        },
    },
]


def _utf16_to_codepoint(text: str, utf16_offset: int) -> int:
    """Convert a browser UTF-16 code-unit offset into a Python ``str`` index.

    CodeMirror reports positions as UTF-16 code units; Python strings index by
    Unicode code point. For the (rare) case where a character lives outside the
    BMP, the two diverge, so walk the string counting UTF-16 units per code
    point. Out-of-range offsets are clamped to the string bounds.
    """
    utf16_offset = max(0, utf16_offset)
    units = 0
    index = 0
    while index < len(text) and units < utf16_offset:
        code_point_units = 1 if ord(text[index]) < 0x10000 else 2
        if units + code_point_units > utf16_offset:
            break
        units += code_point_units
        index += 1
    return index


def insert_latex(resume: Resume, args: dict, cursor: int | None) -> dict:
    code = args["code"]
    if cursor is None:
        resume.main_tex = resume.main_tex + code
    else:
        pos = _utf16_to_codepoint(resume.main_tex, cursor)
        resume.main_tex = resume.main_tex[:pos] + code + resume.main_tex[pos:]
    resume.save(update_fields=["main_tex", "updated_at"])
    return {"success": True, "message": "Code inserted at cursor position"}


def replace_selection(
    resume: Resume,
    args: dict,
    cursor: int | None,
    selection: dict | None,
) -> dict:
    if selection is None:
        return {"success": False, "error": "No text is currently selected in the editor"}
    code = args["code"]
    start = _utf16_to_codepoint(resume.main_tex, selection["start"])
    end = _utf16_to_codepoint(resume.main_tex, selection["end"])
    resume.main_tex = resume.main_tex[:start] + code + resume.main_tex[end:]
    resume.save(update_fields=["main_tex", "updated_at"])
    return {"success": True, "message": "Selection replaced with code"}


def find_and_replace(resume: Resume, args: dict) -> dict:
    find = args["find"]
    replace = args["replace"]
    replaced = resume.main_tex.replace(find, replace)
    if replaced == resume.main_tex:
        return {"success": False, "error": f'Could not find "{find}" in the document'}
    resume.main_tex = replaced
    resume.save(update_fields=["main_tex", "updated_at"])
    return {"success": True, "message": f'Replaced "{find}" with "{replace}"'}


TOOL_EXECUTORS = {
    "insert_latex": insert_latex,
    "replace_selection": replace_selection,
    "find_and_replace": find_and_replace,
}
