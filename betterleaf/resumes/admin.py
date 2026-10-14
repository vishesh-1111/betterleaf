from django.contrib import admin

from betterleaf.resumes.models import Compilation
from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import ResumeEditProposal
from betterleaf.resumes.models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "expires_at", "created_at")
    search_fields = ("id",)
    raw_id_fields = ("user",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "template", "workspace", "updated_at")
    search_fields = ("title", "slug")
    raw_id_fields = ("workspace",)


@admin.register(Compilation)
class CompilationAdmin(admin.ModelAdmin):
    list_display = ("id", "resume", "status", "created_at", "finished_at")
    list_filter = ("status",)
    raw_id_fields = ("resume",)


@admin.register(ResumeEditProposal)
class ResumeEditProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "resume", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("resume",)
