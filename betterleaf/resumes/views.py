from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.resumes.auth import ANONYMOUS_WORKSPACE_TTL
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.permissions import HasWorkspace
from betterleaf.resumes.serializers import CompilationSerializer
from betterleaf.resumes.serializers import ResumeListSerializer
from betterleaf.resumes.serializers import ResumeSerializer
from betterleaf.resumes.serializers import TemplateSerializer
from betterleaf.resumes.tasks import compile_resume


class WorkspaceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        workspace = get_workspace(request)
        if workspace is not None:
            data = {
                "workspace_id": str(workspace.id),
                "anonymous": workspace.user_id is None,
            }
            return Response(data)
        raw, token_hash = new_anonymous_token()
        workspace = Workspace.objects.create(
            anonymous_token_hash=token_hash,
            expires_at=timezone.now() + ANONYMOUS_WORKSPACE_TTL,
        )
        response = Response(
            {"workspace_id": str(workspace.id), "anonymous": True},
            status=status.HTTP_201_CREATED,
        )
        response.set_cookie(
            "bl_session",
            raw,
            max_age=int(ANONYMOUS_WORKSPACE_TTL.total_seconds()),
            httponly=True,
            samesite="Lax",
        )
        return response


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
