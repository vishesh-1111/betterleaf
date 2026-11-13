import base64
import io

from celery.result import AsyncResult
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.resumes.auth import get_or_create_workspace
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.auth import set_workspace_cookie
from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.permissions import HasWorkspace
from betterleaf.resumes.serializers import CompilationListSerializer
from betterleaf.resumes.serializers import CompilationSerializer
from betterleaf.resumes.serializers import PdfUploadSerializer
from betterleaf.resumes.serializers import ResumeListSerializer
from betterleaf.resumes.serializers import ResumeSerializer
from betterleaf.resumes.serializers import TemplateSerializer
from betterleaf.resumes.services.compiler import run_compilation
from betterleaf.resumes.tasks import parse_and_create_master


class WorkspaceAPIView(APIView):
    """Base for the SPA's session-bootstrap endpoints (reachable by guests).

    * Forces a csrftoken cookie onto the response so the SPA can echo it back
      as X-CSRFToken on subsequent unsafe API calls.
    * ``get_or_create_workspace()`` resolves the caller's workspace (signed-in
      user's, else the guest's), minting a guest workspace if there is none.
      When it does, the ``bl_session`` cookie is set on the response.
    """

    permission_classes = [AllowAny]
    new_guest_token: str | None = None

    def initial(self, request, *args, **kwargs):
        get_token(request)
        super().initial(request, *args, **kwargs)

    def get_or_create_workspace(self) -> Workspace:
        workspace, self.new_guest_token = get_or_create_workspace(self.request)
        return workspace

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if self.new_guest_token is not None:
            set_workspace_cookie(response, self.new_guest_token)
        return response


class UserStatusView(WorkspaceAPIView):
    def get(self, request):
        user = getattr(request, "user", None)
        return Response(
            {
                "authenticated": user is not None and user.is_authenticated,
                "has_workspace": get_workspace(request) is not None,
            },
        )


class UploadPdfView(WorkspaceAPIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        # Validate before resolving the workspace so a bad upload never
        # creates a guest workspace.
        serializer = PdfUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        workspace = self.get_or_create_workspace()
        task = parse_and_create_master.delay(
            workspace_id=str(workspace.id),
            file_b64=base64.b64encode(upload.read()).decode("utf-8"),
            filename=upload.name,
        )

        created = self.new_guest_token is not None
        return Response(
            {"task_id": task.id, "status": "queued", "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UploadStatusView(WorkspaceAPIView):
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
        workspace = get_workspace(request)
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


class WorkspaceView(WorkspaceAPIView):
    permission_classes = [HasWorkspace]

    def get(self, request):
        workspace = get_workspace(request)
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
        workspace = get_workspace(self.request)
        if workspace is None:
            return Resume.objects.none()
        return Resume.objects.filter(workspace=workspace)

    def get_serializer_class(self):
        if self.action == "list":
            return ResumeListSerializer
        return ResumeSerializer

    def perform_create(self, serializer):
        workspace = get_workspace(self.request)
        template = TEMPLATE_CATALOG[serializer.validated_data["template"]]
        serializer.save(
            workspace=workspace,
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
        workspace = get_workspace(self.request)
        if workspace is None:
            return Compilation.objects.none()
        return Compilation.objects.filter(resume__workspace=workspace)
