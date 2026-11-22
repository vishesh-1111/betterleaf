from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import TailorRequest
from betterleaf.resumes.services.schemas import ResumeData
from betterleaf.resumes.services.tailor.master_update import BULLET_SECTIONS
from betterleaf.resumes.services.tailor.master_view import answer_targets
from betterleaf.resumes.services.tailor.schemas import Requirement
from betterleaf.resumes.services.tailor.scores import score_requirements


MAX_PDF_UPLOAD_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"


class PdfUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, upload):
        if not upload.name.lower().endswith(".pdf"):
            message = "Only PDF files are supported."
            raise serializers.ValidationError(message)
        if upload.size > MAX_PDF_UPLOAD_BYTES:
            limit_mb = MAX_PDF_UPLOAD_BYTES // (1024 * 1024)
            message = f"File too large (max {limit_mb} MB)."
            raise serializers.ValidationError(message)
        if upload.read(len(PDF_MAGIC)) != PDF_MAGIC:
            message = "File is not a valid PDF."
            raise serializers.ValidationError(message)
        upload.seek(0)
        return upload


class TemplateSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()


class MasterResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterResume
        fields = [
            "id",
            "title",
            "structured_data",
            "parsed_from_file",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "structured_data",
            "updated_at",
        ]


class TailorRequestIdMixin(serializers.Serializer):
    """Adds ``tailor_request_id``: the job this resume was tailored for, if any.

    Lets the Review tab find its report again after a reload. Querysets should
    ``select_related("tailor_request")`` to avoid one query per resume.
    """

    tailor_request_id = serializers.SerializerMethodField()

    def get_tailor_request_id(self, resume):
        try:
            return str(resume.tailor_request.id)
        except ObjectDoesNotExist:
            return None


class ResumeSerializer(TailorRequestIdMixin, serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "title",
            "slug",
            "template",
            "main_tex",
            "structured_data",
            "tailor_request_id",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "updated_at",
        ]

    def validate_structured_data(self, value):
        """Accept only a well-formed resume; fill any missing ids."""
        try:
            return ResumeData.model_validate(value).model_dump(mode="json")
        except ValueError as exc:
            message = f"Invalid resume data: {exc}"
            raise serializers.ValidationError(message) from exc

    def validate_template(self, value):
        if value not in TEMPLATE_CATALOG:
            message = f"Unknown template: {value}"
            raise serializers.ValidationError(message)
        return value


class ResumeListSerializer(TailorRequestIdMixin, serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "title",
            "slug",
            "template",
            "main_tex",
            "structured_data",
            "tailor_request_id",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "updated_at"]


class CompilationListSerializer(serializers.ModelSerializer):
    """Light shape for listings: omits the (large) base64 PDF."""

    class Meta:
        model = Compilation
        fields = ["id", "status", "log", "created_at", "finished_at"]


class CompilationSerializer(CompilationListSerializer):
    class Meta(CompilationListSerializer.Meta):
        fields = [*CompilationListSerializer.Meta.fields, "pdf_base64"]


class TailorRequestCreateSerializer(serializers.Serializer):
    job_text = serializers.CharField(trim_whitespace=True)


class GapAnswerSerializer(serializers.Serializer):
    requirement_id = serializers.CharField()
    source_type = serializers.ChoiceField(choices=BULLET_SECTIONS)
    item_id = serializers.CharField()
    text = serializers.CharField(trim_whitespace=True)


class GapAnswersSerializer(serializers.Serializer):
    answers = GapAnswerSerializer(many=True, allow_empty=False)


class AcceptedProposalSerializer(serializers.Serializer):
    """A proposal the user kept, with their final (possibly edited) wording."""

    id = serializers.CharField()
    bullet = serializers.CharField(trim_whitespace=True)
    skill = serializers.CharField(required=False, allow_blank=True, default="")
    skill_group_id = serializers.CharField(required=False, allow_blank=True, default="")


class ConfirmSerializer(serializers.Serializer):
    accepted = AcceptedProposalSerializer(many=True)


class TailorRequestSerializer(serializers.ModelSerializer):
    """Poll shape: just id/status until ready, then the coverage report."""

    class Meta:
        model = TailorRequest
        fields = ["id", "status", "kind", "job_text"]

    def to_representation(self, instance):
        body = super().to_representation(instance)
        body["parent_id"] = str(instance.parent_id) if instance.parent_id else None
        Status = TailorRequest.Status  # noqa: N806
        if instance.status == Status.FAILED:
            body["error"] = instance.error
        elif instance.status in (Status.READY, Status.DRAFTING):
            requirements = instance.result.get("requirements", [])
            body["resume_id"] = str(instance.resume_id) if instance.resume_id else None
            body["scores"] = score_requirements(
                [Requirement.model_validate(r) for r in requirements],
            )
            body["requirements"] = requirements
            body["gap_questions"] = instance.result.get("gap_questions", [])
            body["answer_targets"] = answer_targets(
                instance.master_resume.structured_data,
            )
            body["proposals"] = instance.proposals
            if instance.status == Status.READY and instance.error:
                body["error"] = instance.error
        return body
