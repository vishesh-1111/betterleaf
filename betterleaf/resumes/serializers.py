from rest_framework import serializers

from betterleaf.resumes.catalog import TEMPLATE_CATALOG
from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import Resume


class TemplateSerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()


class ResumeSerializer(serializers.ModelSerializer):
    latest_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = [
            "id",
            "title",
            "slug",
            "template",
            "main_tex",
            "updated_at",
            "latest_pdf_url",
        ]
        read_only_fields = ["id", "slug", "updated_at", "latest_pdf_url"]

    def validate_template(self, value):
        if value not in TEMPLATE_CATALOG:
            message = f"Unknown template: {value}"
            raise serializers.ValidationError(message)
        return value

    def get_latest_pdf_url(self, obj):
        latest = (
            Compilation.objects.filter(resume=obj, status=Compilation.Status.SUCCEEDED)
            .exclude(pdf="")
            .order_by("-finished_at")
            .first()
        )
        if latest is None or not latest.pdf:
            return None
        return latest.pdf.url


class ResumeListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resume
        fields = ["id", "title", "slug", "template", "updated_at"]
        read_only_fields = ["id", "slug", "updated_at"]


class CompilationSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Compilation
        fields = ["id", "status", "pdf_url", "log", "created_at", "finished_at"]

    def get_pdf_url(self, obj):
        if not obj.pdf:
            return None
        return obj.pdf.url
