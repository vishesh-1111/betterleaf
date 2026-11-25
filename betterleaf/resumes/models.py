import uuid

from django.conf import settings
from django.db import models
from slugify import slugify


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="workspace",
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


class MasterResume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.OneToOneField(
        Workspace, on_delete=models.CASCADE, related_name="master_resume",
    )
    title = models.CharField(max_length=200)
    structured_data = models.JSONField(blank=True, default=dict)
    parsed_from_file = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="resumes",
    )
    master_resume = models.ForeignKey(
        MasterResume, on_delete=models.CASCADE, related_name="resumes", null=True, blank=True,
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
    # Compiled PDF, base64-encoded (ASCII). Kept in the row so deploys need no
    # media storage and the compile response can return it directly.
    pdf_base64 = models.TextField(blank=True, default="")
    # Compiler exit code (0 == clean). Independent of PDF availability: TeX can
    # exit non-zero yet still emit a PDF (nonstopmode without halt-on-error).
    exit_status = models.IntegerField(null=True, blank=True)
    log = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Compilation {self.id} [{self.status}]"


class TailorRequest(models.Model):
    class Status(models.TextChoices):
        ANALYSING = "analysing", "Analysing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        # The AI is turning the user's gap answers into proposed bullets.
        DRAFTING = "drafting", "Drafting"

    class Kind(models.TextChoices):
        INITIAL = "initial", "Initial"
        GAP_FOLLOWUP = "gap_followup", "Gap follow-up"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="tailor_requests",
    )
    # Empty for the first request on a job; follow-ups point at their source.
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="followups",
    )
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.INITIAL,
    )
    master_resume = models.ForeignKey(
        MasterResume, on_delete=models.CASCADE, related_name="tailor_requests",
    )
    job_text = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ANALYSING,
    )
    # Checked AI answer: requirements (with evidence) and gap questions.
    result = models.JSONField(blank=True, default=dict)
    # What the user typed for each gap (skipped gaps are left out).
    answers = models.JSONField(blank=True, default=list)
    # Bullets the AI drafted from the answers, waiting for the user's review.
    proposals = models.JSONField(blank=True, default=list)
    # Gaps already answered or skipped, by requirement text, so a follow-up
    # does not ask them again.
    handled_gaps = models.JSONField(blank=True, default=list)
    resume = models.OneToOneField(
        Resume,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tailor_request",
    )
    # Set when the request succeeds; the free limit will count these later.
    counted = models.BooleanField(default=False)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"TailorRequest {self.id} [{self.status}]"
