from celery import shared_task

from betterleaf.resumes.models import Compilation, MasterResume, Resume
from betterleaf.resumes.services.parsing import parse_resume_upload
from betterleaf.resumes.services.latex import render_resume


def handle_existing_master_upload(
    workspace_id: str, file_b64: str, filename: str,
) -> str:
    """
    Handle an upload when the workspace already has a MasterResume.

    TODO: decide the behaviour (replace, merge into, or create an additional
    master resume).
    """
    raise NotImplementedError(
        "Uploading a resume to a workspace that already has a master resume "
        "is not supported yet.",
    )


@shared_task(bind=True)
def parse_and_create_master(self, workspace_id: str, file_b64: str, filename: str) -> str:
    """
    Extract resume from PDF and create MasterResume and Resume.

    If the workspace already has a MasterResume, the upload is delegated to
    `handle_existing_master_upload` (not implemented yet).

    Args:
        workspace_id: UUID of workspace
        file_b64: PDF content as base64-encoded string
        filename: Original filename

    Returns:
        MasterResume.id
    """
    import base64

    # Checked outside the try block so NotImplementedError isn't retried.
    if MasterResume.objects.filter(workspace_id=workspace_id).exists():
        return handle_existing_master_upload(workspace_id, file_b64, filename)

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
