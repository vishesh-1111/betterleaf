from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.services.compiler import LatexCompileError
from betterleaf.resumes.services.compiler import compile_latex


@shared_task
def compile_resume(compilation_id: str) -> None:
    try:
        compilation = Compilation.objects.select_related("resume").get(
            id=compilation_id,
        )
    except Compilation.DoesNotExist:
        return
    resume = compilation.resume
    compilation.status = Compilation.Status.RUNNING
    compilation.save(update_fields=["status"])

    try:
        template = TEMPLATE_CATALOG[resume.template]
    except KeyError:
        compilation.status = Compilation.Status.FAILED
        compilation.log = f"Unknown template: {resume.template}"
        compilation.finished_at = timezone.now()
        compilation.save()
        return

    extra_files: dict[str, bytes] = {}
    if template.cls_path is not None:
        extra_files["resume.cls"] = template.cls_path.read_bytes()

    try:
        status, log, pdf = compile_latex(
            resume.main_tex, extra_files=extra_files,
        )
    except LatexCompileError as exc:
        compilation.status = Compilation.Status.FAILED
        compilation.log = str(exc)
        compilation.finished_at = timezone.now()
        compilation.save()
        return

    if status == 0 and pdf:
        compilation.pdf.save(
            f"{resume.slug}.pdf", ContentFile(pdf), save=False,
        )
        compilation.status = Compilation.Status.SUCCEEDED
    else:
        compilation.status = Compilation.Status.FAILED
    compilation.log = log
    compilation.finished_at = timezone.now()
    compilation.save()
