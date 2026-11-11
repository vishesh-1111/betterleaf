import base64

from django.http import FileResponse
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework import viewsets
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
from betterleaf.resumes.serializers import CompilationSerializer
from betterleaf.resumes.serializers import PdfUploadSerializer
from betterleaf.resumes.serializers import ResumeListSerializer
from betterleaf.resumes.serializers import ResumeSerializer
from betterleaf.resumes.serializers import TemplateSerializer
from betterleaf.resumes.tasks import compile_resume
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
        compile_resume.delay(str(compilation.id))
        return Response(
            {"id": str(compilation.id), "status": compilation.status},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        resume = self.get_object()
        latest = (
            Compilation.objects.filter(
                resume=resume, status=Compilation.Status.SUCCEEDED,
            )
            .exclude(pdf="")
            .order_by("-finished_at")
            .first()
        )
        if latest is None or not latest.pdf:
            return Response(
                {"detail": "No compiled PDF available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        latest.pdf.open("rb")
        return FileResponse(
            latest.pdf,
            as_attachment=True,
            filename=f"{resume.slug}.pdf",
            content_type="application/pdf",
        )


class CompilationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [HasWorkspace]
    serializer_class = CompilationSerializer

    def get_queryset(self):
        workspace = get_workspace(self.request)
        if workspace is None:
            return Compilation.objects.none()
        return Compilation.objects.filter(resume__workspace=workspace)
