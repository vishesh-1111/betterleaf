import shutil
import subprocess
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation

TECTONIC_TIMEOUT = 30


@shared_task
def compile_resume(compilation_id: str) -> None:
    try:
        compilation = Compilation.objects.select_related("resume").get(id=compilation_id)
    except Compilation.DoesNotExist:
        return
    resume = compilation.resume
    compilation.status = Compilation.Status.RUNNING
    compilation.save(update_fields=["status"])
    template = TEMPLATE_CATALOG[resume.template]
    tmpdir = Path(tempfile.mkdtemp(prefix="betterleaf-compile-"))
    try:
        (tmpdir / "main.tex").write_text(resume.main_tex)
        if template.cls_path is not None:
            shutil.copy(template.cls_path, tmpdir / "resume.cls")
        proc = subprocess.run(
            ["tectonic", "--outdir", str(tmpdir), "main.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=TECTONIC_TIMEOUT,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
        pdf_path = tmpdir / "main.pdf"
        if proc.returncode == 0 and pdf_path.exists():
            compilation.pdf.save(f"{resume.slug}.pdf", ContentFile(pdf_path.read_bytes()), save=False)
            compilation.status = Compilation.Status.SUCCEEDED
        else:
            compilation.status = Compilation.Status.FAILED
        compilation.log = log
        compilation.finished_at = timezone.now()
        compilation.save()
    except subprocess.TimeoutExpired:
        compilation.status = Compilation.Status.FAILED
        compilation.log = f"Compilation timed out after {TECTONIC_TIMEOUT}s."
        compilation.finished_at = timezone.now()
        compilation.save()
    except KeyError:
        compilation.status = Compilation.Status.FAILED
        compilation.log = f"Unknown template: {resume.template}"
        compilation.finished_at = timezone.now()
        compilation.save()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
