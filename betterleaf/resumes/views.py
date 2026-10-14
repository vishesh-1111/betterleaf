from django.http import FileResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from betterleaf.resumes.auth import ANONYMOUS_WORKSPACE_TTL
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import ResumeEditProposal
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.permissions import HasWorkspace
from betterleaf.resumes.serializers import CompilationSerializer
from betterleaf.resumes.serializers import ProposalSerializer
from betterleaf.resumes.serializers import ResumeListSerializer
from betterleaf.resumes.serializers import ResumeSerializer
from betterleaf.resumes.serializers import TemplateSerializer
from betterleaf.resumes.services import proposals as proposal_service
from betterleaf.resumes.services.extract import pdf_to_text
from betterleaf.resumes.services.latex import render_resume
from betterleaf.resumes.services.parser import ResumeParseError
from betterleaf.resumes.services.parser import extract_resume
from betterleaf.resumes.services.rewrite import rewrite_resume
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.tasks import compile_resume


class UserStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Force a csrftoken cookie onto the response so the SPA can echo it
        # back as X-CSRFToken on subsequent unsafe API calls.
        get_token(request)
        user = getattr(request, "user", None)
        authenticated = user is not None and user.is_authenticated
        workspace = get_workspace(request)
        return Response(
            {
                "authenticated": authenticated,
                "has_workspace": workspace is not None,
            },
        )


class UploadPdfView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser]

    def post(self, request):
        # Force a csrftoken cookie on the response so the SPA can echo it back
        # as X-CSRFToken on subsequent unsafe API calls.
        get_token(request)

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"detail": "Missing 'file' part in multipart upload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            pdf_bytes = upload.read()
        except OSError as exc:
            return Response(
                {"detail": f"Failed to read upload: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse before touching the workspace so a bad PDF can't leave an
        # orphaned anonymous workspace behind.
        try:
            markdown = pdf_to_text(pdf_bytes)
            data = extract_resume(markdown)
            tex = render_resume(data)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ResumeParseError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        workspace = get_workspace(request)
        created = workspace is None
        raw = None
        if workspace is None:
            raw, token_hash = new_anonymous_token()
            workspace = Workspace.objects.create(
                anonymous_token_hash=token_hash,
                expires_at=timezone.now() + ANONYMOUS_WORKSPACE_TTL,
            )

        title = upload.name.rsplit(".", 1)[0].strip() or "Resume"
        resume = Resume.objects.create(
            workspace=workspace,
            title=title,
            template="jakes",
            main_tex=tex,
            structured_data=data.model_dump(),
        )

        data_rsp = {"resume": ResumeSerializer(resume).data, "created": created}
        if not created:
            return Response(data_rsp)
        response = Response(data_rsp, status=status.HTTP_201_CREATED)
        response.set_cookie(
            "bl_session",
            raw,
            max_age=int(ANONYMOUS_WORKSPACE_TTL.total_seconds()),
            httponly=True,
            samesite="Lax",
        )
        return response


class WorkspaceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # Force a csrftoken cookie onto the response so the SPA can echo it
        # back as X-CSRFToken on subsequent unsafe API calls.
        get_token(request)
        workspace = get_workspace(request)
        created = workspace is None
        if workspace is None:
            raw, token_hash = new_anonymous_token()
            workspace = Workspace.objects.create(
                anonymous_token_hash=token_hash,
                expires_at=timezone.now() + ANONYMOUS_WORKSPACE_TTL,
            )
        resumes = ResumeListSerializer(
            Resume.objects.filter(workspace=workspace),
            many=True,
        ).data
        data = {
            "workspace_id": str(workspace.id),
            "anonymous": workspace.user_id is None,
            "resumes": resumes,
        }
        if not created:
            return Response(data)
        response = Response(data, status=status.HTTP_201_CREATED)
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
            resume=resume,
            status=Compilation.Status.QUEUED,
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
                resume=resume,
                status=Compilation.Status.SUCCEEDED,
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


class ProposalViewSet(viewsets.GenericViewSet):
    """List resumes' edit proposals; create/accept/reject via actions."""

    permission_classes = [HasWorkspace]
    serializer_class = ProposalSerializer

    def get_queryset(self):
        workspace = get_workspace(self.request)
        if workspace is None:
            return ResumeEditProposal.objects.none()
        return ResumeEditProposal.objects.filter(resume__workspace=workspace)

    @action(detail=False, methods=["post"])
    def create_proposal(self, request):
        """Rewrite a resume via the LLM and store the diff as a proposal."""
        resume_id = request.data.get("resume")
        prompt = (request.data.get("prompt") or "").strip()
        if not resume_id or not prompt:
            return Response(
                {"detail": "Both 'resume' and 'prompt' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resume = Resume.objects.get(
                id=resume_id,
                workspace__user=request.user,
            )
        except Resume.DoesNotExist:
            return Response(
                {"detail": "Resume not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        current = ResumeData.model_validate(resume.structured_data)
        try:
            new_data = rewrite_resume(current, prompt)
        except ResumeParseError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        changes = proposal_service.diff(
            current.model_dump(),
            new_data.model_dump(),
        )
        for ch in changes:
            ch["id"] = proposal_service.new_id()
            ch["status"] = "pending"

        proposal = ResumeEditProposal.objects.create(
            resume=resume,
            prompt=prompt,
            changes=changes,
        )
        return Response(
            ProposalSerializer(proposal).data,
            status=status.HTTP_201_CREATED,
        )

    def _get_proposal(self, pk):
        workspace = get_workspace(self.request)
        try:
            return ResumeEditProposal.objects.get(
                pk=pk,
                resume__workspace=workspace,
            )
        except ResumeEditProposal.DoesNotExist:
            return None

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        proposal = self._get_proposal(pk)
        if proposal is None:
            return Response(
                {"detail": "Proposal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        change_ids = request.data.get("change_ids") or []
        if not isinstance(change_ids, list):
            return Response(
                {"detail": "'change_ids' must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_service.accept(proposal, [str(c) for c in change_ids])
        return Response(ProposalSerializer(proposal).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        proposal = self._get_proposal(pk)
        if proposal is None:
            return Response(
                {"detail": "Proposal not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        change_ids = request.data.get("change_ids") or []
        if not isinstance(change_ids, list):
            return Response(
                {"detail": "'change_ids' must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        proposal_service.reject(proposal, [str(c) for c in change_ids])
        return Response(ProposalSerializer(proposal).data)
