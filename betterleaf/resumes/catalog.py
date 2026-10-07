from dataclasses import dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "template_src"


@dataclass(frozen=True)
class ResumeTemplate:
    slug: str
    name: str
    starter_tex: Path
    cls_path: Path | None = None  # None = starter.tex is self-contained (no class file)
    attribution: str = ""  # license/provenance note, rendered nowhere in slice 1


def _tex_only(slug: str, name: str) -> ResumeTemplate:
    d = SRC_DIR / slug
    return ResumeTemplate(slug, name, d / "starter.tex", None, "MIT (sb2nov/resume)")


TEMPLATE_CATALOG = {
    "jakes": _tex_only("jakes", "Jake's Resume"),
}
