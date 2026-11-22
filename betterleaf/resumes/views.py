import base64
import io

from celery.result import AsyncResult
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import FileResponse
from django.middleware.csrf import get_token
from rest_framework import mixins
from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.resumes.auth import get_or_create_workspace
from betterleaf.resumes.auth import set_workspace_cookie
from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import TailorRequest
from betterleaf.resumes.permissions import HasWorkspace
from betterleaf.resumes.serializers import CompilationListSerializer
from betterleaf.resumes.serializers import CompilationSerializer
from betterleaf.resumes.serializers import ConfirmSerializer
from betterleaf.resumes.serializers import GapAnswersSerializer
from betterleaf.resumes.serializers import PdfUploadSerializer
from betterleaf.resumes.serializers import ResumeListSerializer
from betterleaf.resumes.serializers import ResumeSerializer
from betterleaf.resumes.serializers import TailorRequestCreateSerializer
from betterleaf.resumes.serializers import TailorRequestSerializer
from betterleaf.resumes.serializers import TemplateSerializer
from betterleaf.resumes.services.compiler import run_compilation
from betterleaf.resumes.services.tailor.gap_answers import GapAnswerError
from betterleaf.resumes.services.tailor.gap_answers import handled_gaps_after
from betterleaf.resumes.services.tailor.gap_answers import validate_answers
from betterleaf.resumes.services.tailor.master_update import MasterUpdateError
from betterleaf.resumes.services.tailor.master_update import apply_proposals
from betterleaf.resumes.tasks import analyse_job
from betterleaf.resumes.tasks import draft_gap_proposals
from betterleaf.resumes.tasks import parse_and_create_master


class CsrfCookieAPIView(APIView):
    """Base for the SPA's session-bootstrap endpoints (reachable by guests).

    Forces a csrftoken cookie onto the response so the SPA can echo it back
    as X-CSRFToken on subsequent unsafe API calls. The caller's workspace is
    ``request.workspace``, resolved by ``WorkspaceMiddleware``.
    """

    def initial(self, request, *args, **kwargs):
        get_token(request)
        super().initial(request, *args, **kwargs)


class UserStatusView(CsrfCookieAPIView):
    def get(self, request):
        user = getattr(request, "user", None)
        return Response(
            {
                "authenticated": user is not None and user.is_authenticated,
                "has_workspace": request.workspace is not None,
            },
        )


class UploadPdfView(CsrfCookieAPIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        # Validate before getting/creating the workspace so a bad upload never
        # creates a guest workspace.
        serializer = PdfUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        workspace, new_guest_token = get_or_create_workspace(request)
        task = parse_and_create_master.delay(
            workspace_id=str(workspace.id),
            file_b64=base64.b64encode(upload.read()).decode("utf-8"),
            filename=upload.name,
        )

        created = new_guest_token is not None
        response = Response(
            {"task_id": task.id, "status": "queued", "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
        if created:
            set_workspace_cookie(response, new_guest_token)
        return response


class UploadStatusView(CsrfCookieAPIView):
    """Poll the progress of a task queued by ``UploadPdfView``.

    ``status`` is one of ``queued`` | ``processing`` | ``succeeded`` | ``failed``.
    On success the response carries ``master_resume_id`` and ``resume_ids``;
    on failure a generic ``error`` (the raw exception is never exposed).
    Tasks belonging to another workspace look identical to unknown ones (404).
    """

    permission_classes = [HasWorkspace]

    # Celery state -> API status. PENDING is also what Celery reports for
    # unknown ids, so it is indistinguishable from "queued".
    STATUS_BY_STATE = {
        "PENDING": "queued",
        "RECEIVED": "queued",
        "STARTED": "processing",
        "RETRY": "processing",
        "SUCCESS": "succeeded",
        "FAILURE": "failed",
        "REVOKED": "failed",
    }

    def get(self, request, task_id):
        workspace = request.workspace
        result = AsyncResult(task_id)
        state = result.state

        # With CELERY_RESULT_EXTENDED the task kwargs are stored alongside the
        # state, so we can verify ownership once the worker has picked it up.
        kwargs = result.kwargs if isinstance(result.kwargs, dict) else {}
        owner_id = kwargs.get("workspace_id")
        if owner_id is not None and owner_id != str(workspace.id):
            raise NotFound

        task_status = self.STATUS_BY_STATE.get(state, "processing")
        body = {"task_id": task_id, "status": task_status}

        if state == "SUCCESS":
            try:
                master = workspace.master_resume
            except ObjectDoesNotExist:
                raise NotFound from None
            body["master_resume_id"] = str(master.id)
            body["resume_ids"] = [
                str(pk) for pk in master.resumes.values_list("id", flat=True)
            ]
        elif task_status == "failed":
            body["error"] = "Failed to process the uploaded resume."

        return Response(body)


class WorkspaceView(CsrfCookieAPIView):
    permission_classes = [HasWorkspace]

    def get(self, request):
        workspace = request.workspace
        resumes = ResumeListSerializer(
            Resume.objects.filter(workspace=workspace), many=True,
        ).data
        return Response(
            {
                "workspace_id": str(workspace.id),
                "anonymous": workspace.user_id is None,
                "resumes": resumes,
            },
        )


class TemplateListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(TemplateSerializer(TEMPLATE_CATALOG.values(), many=True).data)


class ResumeViewSet(viewsets.ModelViewSet):
    permission_classes = [HasWorkspace]

    def get_queryset(self):
        return Resume.objects.filter(workspace=self.request.workspace)

    def get_serializer_class(self):
        if self.action == "list":
            return ResumeListSerializer
        return ResumeSerializer

    def perform_create(self, serializer):
        template = TEMPLATE_CATALOG[serializer.validated_data["template"]]
        serializer.save(
            workspace=self.request.workspace,
            main_tex=template.starter_tex.read_text(),
        )

    @action(detail=True, methods=["post"])
    def compile(self, request, pk=None):
        resume = self.get_object()
        if not resume.main_tex.strip():
            return Response(
                {"detail": "Resume has no content."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        compilation = Compilation.objects.create(
            resume=resume, status=Compilation.Status.QUEUED,
        )
        run_compilation(compilation)
        compilation.refresh_from_db()
        return Response(
            CompilationSerializer(compilation).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        resume = self.get_object()
        latest = (
            Compilation.objects.filter(
                resume=resume, status=Compilation.Status.SUCCEEDED,
            )
            .exclude(pdf_base64="")
            .order_by("-finished_at")
            .first()
        )
        if latest is None:
            return Response(
                {"detail": "No compiled PDF available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            io.BytesIO(base64.b64decode(latest.pdf_base64)),
            as_attachment=True,
            filename=f"{resume.slug}.pdf",
            content_type="application/pdf",
        )


class CompilationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasWorkspace]

    def get_serializer_class(self):
        if self.action == "list":
            return CompilationListSerializer
        return CompilationSerializer

    def get_queryset(self):
        return Compilation.objects.filter(resume__workspace=self.request.workspace)


class TailorRequestViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Start a tailoring run for a job description and poll for the result."""

    permission_classes = [HasWorkspace]
    serializer_class = TailorRequestSerializer

    def get_queryset(self):
        return TailorRequest.objects.filter(workspace=self.request.workspace)

    def create(self, request, *args, **kwargs):
        body = TailorRequestCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        try:
            master = request.workspace.master_resume
        except ObjectDoesNotExist:
            return Response(
                {"detail": "Upload a resume before tailoring."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tailor = TailorRequest.objects.create(
            workspace=request.workspace,
            master_resume=master,
            job_text=body.validated_data["job_text"],
        )
        transaction.on_commit(lambda: analyse_job.delay(str(tailor.id)))
        return Response(
            {"id": str(tailor.id), "status": tailor.status},
            status=status.HTTP_202_ACCEPTED,
        )

    def _not_ready(self, tailor):
        if tailor.status != TailorRequest.Status.READY:
            return Response(
                {"detail": "This request is not ready for answers yet."},
                status=status.HTTP_409_CONFLICT,
            )
        return None

    @action(detail=True, methods=["post"])
    def answers(self, request, pk=None):
        """Save the user's gap answers and queue the AI to draft bullets."""
        tailor = self.get_object()
        if (blocked := self._not_ready(tailor)) is not None:
            return blocked
        body = GapAnswersSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        answers = body.validated_data["answers"]
        try:
            validate_answers(
                answers,
                tailor.master_resume.structured_data,
                tailor.result.get("gap_questions", []),
            )
        except GapAnswerError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        tailor.answers = answers
        tailor.proposals = []
        tailor.error = ""
        tailor.status = TailorRequest.Status.DRAFTING
        tailor.save(
            update_fields=["answers", "proposals", "error", "status", "updated_at"],
        )
        transaction.on_commit(lambda: draft_gap_proposals.delay(str(tailor.id)))
        return Response(
            {"id": str(tailor.id), "status": tailor.status},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Save the accepted bullets into the master and tailor again."""
        tailor = self.get_object()
        if (blocked := self._not_ready(tailor)) is not None:
            return blocked
        body = ConfirmSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        accepted = body.validated_data["accepted"]
        if not accepted:
            return Response(
                {"id": str(tailor.id), "status": tailor.status},
                status=status.HTTP_200_OK,
            )

        proposals = {p["id"]: p for p in tailor.proposals}
        entries = []
        for item in accepted:
            proposal = proposals.get(item["id"])
            if proposal is None or proposal["change"] != "add_bullet":
                return Response(
                    {"detail": f"Unknown proposal {item['id']!r}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Where the bullet goes comes from the stored proposal, not the client.
            entries.append(
                {
                    "source_type": proposal["source_type"],
                    "item_id": proposal["item_id"],
                    "bullet": item["bullet"],
                    "skill": item["skill"],
                    "skill_group_id": item["skill_group_id"],
                },
            )

        try:
            with transaction.atomic():
                master = MasterResume.objects.select_for_update().get(
                    pk=tailor.master_resume_id,
                )
                master.structured_data = apply_proposals(
                    master.structured_data, entries,
                )
                master.save(update_fields=["structured_data", "updated_at"])
                followup = TailorRequest.objects.create(
                    workspace=tailor.workspace,
                    master_resume=master,
                    job_text=tailor.job_text,
                    parent=tailor,
                    kind=TailorRequest.Kind.GAP_FOLLOWUP,
                    handled_gaps=handled_gaps_after(
                        tailor.handled_gaps, tailor.result, tailor.answers,
                    ),
                )
        except MasterUpdateError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        transaction.on_commit(lambda: analyse_job.delay(str(followup.id)))
        return Response(
            {"id": str(followup.id), "status": followup.status},
            status=status.HTTP_202_ACCEPTED,
        )
