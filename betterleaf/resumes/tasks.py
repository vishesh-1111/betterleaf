import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction

from betterleaf.resumes.models import MasterResume, Resume, TailorRequest
from betterleaf.resumes.services.latex import render_resume
from betterleaf.resumes.services.llm import LLMUnavailableError
from betterleaf.resumes.services.parsing import parse_resume_upload
from betterleaf.resumes.services.tailor.analyse import TailoringError
from betterleaf.resumes.services.tailor.analyse import analyse_job_fit
from betterleaf.resumes.services.tailor.assemble import build_tailored_resume_data
from betterleaf.resumes.services.tailor.gap_answers import GapAnswerError
from betterleaf.resumes.services.tailor.gap_answers import draft_proposals
from betterleaf.resumes.services.tailor.master_view import add_missing_ids

logger = logging.getLogger(__name__)


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


TAILOR_MAX_RETRIES = 2
TAILOR_FAILURE_MESSAGES = {
    "timeout": "Analysis took too long. Please try again.",
    "unavailable": "The analysis service is unavailable. Please try again.",
    "unexpected": "Something went wrong while tailoring your resume.",
}


def _mark_tailor_failed(tailor: TailorRequest, message: str) -> None:
    tailor.status = TailorRequest.Status.FAILED
    tailor.error = message
    tailor.save(update_fields=["status", "error", "updated_at"])


@shared_task(bind=True, soft_time_limit=120)
def analyse_job(self, request_id: str) -> None:
    """Score a TailorRequest's job text against the master and build a Resume.

    Marks the request ``ready`` on success or ``failed`` with a plain message.
    Only network trouble is retried (at most ``TAILOR_MAX_RETRIES`` times).
    """
    tailor = TailorRequest.objects.select_related("master_resume").get(pk=request_id)
    master = tailor.master_resume
    try:
        master_data = add_missing_ids(master.structured_data)
        if master_data != master.structured_data:
            master.structured_data = master_data
            master.save(update_fields=["structured_data", "updated_at"])

        analysis = analyse_job_fit(
            tailor.job_text, master_data, handled_gaps=tailor.handled_gaps,
        )
        resume_data = build_tailored_resume_data(master_data, analysis.selection)

        with transaction.atomic():
            resume = Resume.objects.create(
                workspace_id=tailor.workspace_id,
                master_resume=master,
                title=f"{master.title} (tailored)",
                template="jakes",
                main_tex=render_resume(resume_data),
                structured_data=resume_data,
            )
            tailor.resume = resume
            tailor.result = analysis.model_dump(exclude={"selection"})
            tailor.status = TailorRequest.Status.READY
            # Follow-ups on the same job are free; only the first request counts.
            tailor.counted = tailor.kind == TailorRequest.Kind.INITIAL
            tailor.save()
    except LLMUnavailableError as exc:
        if self.request.retries < TAILOR_MAX_RETRIES:
            raise self.retry(exc=exc, countdown=5, max_retries=TAILOR_MAX_RETRIES)
        _mark_tailor_failed(tailor, TAILOR_FAILURE_MESSAGES["unavailable"])
    except TailoringError as exc:
        _mark_tailor_failed(tailor, str(exc))
    except SoftTimeLimitExceeded:
        _mark_tailor_failed(tailor, TAILOR_FAILURE_MESSAGES["timeout"])
    except Exception:
        logger.exception("Tailoring failed for request %s", request_id)
        _mark_tailor_failed(tailor, TAILOR_FAILURE_MESSAGES["unexpected"])


def _finish_drafting(tailor: TailorRequest, proposals: list, error: str = "") -> None:
    """Back to ``ready`` so the report stays visible, with proposals or an error."""
    tailor.proposals = proposals
    tailor.error = error
    tailor.status = TailorRequest.Status.READY
    tailor.save(update_fields=["proposals", "error", "status", "updated_at"])


@shared_task(bind=True, soft_time_limit=120)
def draft_gap_proposals(self, request_id: str) -> None:
    """Turn a TailorRequest's gap answers into proposed master bullets.

    The request returns to ``ready`` either way: with ``proposals`` filled in,
    or with an ``error`` the user can read before answering again. Only
    network trouble is retried (at most ``TAILOR_MAX_RETRIES`` times).
    """
    tailor = TailorRequest.objects.select_related("master_resume").get(pk=request_id)
    try:
        proposals = draft_proposals(
            tailor.job_text,
            tailor.result.get("requirements", []),
            tailor.answers,
            tailor.master_resume.structured_data,
        )
        _finish_drafting(tailor, proposals)
    except LLMUnavailableError as exc:
        if self.request.retries < TAILOR_MAX_RETRIES:
            raise self.retry(exc=exc, countdown=5, max_retries=TAILOR_MAX_RETRIES)
        _finish_drafting(tailor, [], TAILOR_FAILURE_MESSAGES["unavailable"])
    except GapAnswerError as exc:
        _finish_drafting(tailor, [], str(exc))
    except SoftTimeLimitExceeded:
        _finish_drafting(tailor, [], TAILOR_FAILURE_MESSAGES["timeout"])
    except Exception:
        logger.exception("Drafting proposals failed for request %s", request_id)
        _finish_drafting(tailor, [], TAILOR_FAILURE_MESSAGES["unexpected"])
