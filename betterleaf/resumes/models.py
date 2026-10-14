import uuid

from django.conf import settings
from django.db import models
from slugify import slugify


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="workspaces",
    )
    anonymous_token_hash = models.CharField(
        max_length=64, null=True, blank=True, unique=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        if self.user_id is not None:
            return f"Workspace of {self.user_id}"
        return f"Anonymous workspace {self.id}"


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="resumes",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    template = models.CharField(max_length=50)  # slug key into TEMPLATE_CATALOG
    main_tex = models.TextField(blank=True, default="")
    structured_data = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title) or "resume"
        candidate, n = base, 1
        while Resume.objects.filter(slug=candidate).exists():
            candidate = f"{base}-{n}"
            n += 1
        return candidate


class Compilation(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(
        Resume, on_delete=models.CASCADE, related_name="compilations",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED,
    )
    pdf = models.FileField(upload_to="resumes/pdfs/%Y/%m/", null=True, blank=True)
    log = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Compilation {self.id} [{self.status}]"
