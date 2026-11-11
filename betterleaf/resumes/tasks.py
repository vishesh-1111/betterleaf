from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation, MasterResume, Resume
from betterleaf.resumes.services.compiler import LatexCompileError
from betterleaf.resumes.services.compiler import compile_latex
from betterleaf.resumes.services.parsing import parse_resume_upload
from betterleaf.resumes.services.latex import render_resume


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


@shared_task(bind=True)
def parse_and_create_master(self, workspace_id: str, file_b64: str, filename: str) -> str:
    """
    Extract resume from PDF and create MasterResume and Resume.

    Args:
        workspace_id: UUID of workspace
        file_b64: PDF content as base64-encoded string
        filename: Original filename

    Returns:
        MasterResume.id
    """
    import base64
    try:
        file_bytes = base64.b64decode(file_b64)
        structured_data = parse_resume_upload(file_bytes, filename)

        master = MasterResume.objects.create(
            workspace_id=workspace_id,
            title=filename.replace(".pdf", ""),
            structured_data=structured_data,
            parsed_from_file=filename,
        )

        main_tex = render_resume(structured_data)

        Resume.objects.create(
            workspace_id=workspace_id,
            master_resume=master,
            title=master.title,
            template="jakes",
            main_tex=main_tex,
            structured_data=structured_data,
        )

        return str(master.id)

    except Exception as e:
        self.retry(exc=e, countdown=5, max_retries=3)
