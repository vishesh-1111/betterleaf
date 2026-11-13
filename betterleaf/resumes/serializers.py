from rest_framework import serializers

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import MasterResume
from betterleaf.resumes.models import Resume


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


class ResumeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = [
            "id",
            "title",
            "slug",
            "template",
            "main_tex",
            "structured_data",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "updated_at",
            "structured_data",
        ]

    def validate_template(self, value):
        if value not in TEMPLATE_CATALOG:
            message = f"Unknown template: {value}"
            raise serializers.ValidationError(message)
        return value


class ResumeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ["id", "title", "slug", "template", "main_tex", "updated_at"]
        read_only_fields = ["id", "slug", "updated_at"]


class CompilationListSerializer(serializers.ModelSerializer):
    """Light shape for listings: omits the (large) base64 PDF."""

    class Meta:
        model = Compilation
        fields = ["id", "status", "log", "created_at", "finished_at"]


class CompilationSerializer(CompilationListSerializer):
    class Meta(CompilationListSerializer.Meta):
        fields = [*CompilationListSerializer.Meta.fields, "pdf_base64"]
