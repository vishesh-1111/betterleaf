import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from betterleaf.resumes.models import Workspace

ANONYMOUS_WORKSPACE_TTL = timedelta(days=30)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_anonymous_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def get_workspace(request) -> Workspace | None:
    """Resolve the request's workspace: the signed-in user's, else the anonymous
    workspace named by the `bl_session` cookie."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        workspace = Workspace.objects.filter(user=user).order_by("created_at").first()
        if workspace is None:
            workspace = Workspace.objects.create(user=user)
        return workspace
    raw = request.COOKIES.get("bl_session")
    if not raw:
        return None
    try:
        workspace = Workspace.objects.get(anonymous_token_hash=hash_token(raw))
    except Workspace.DoesNotExist:
        return None
    if workspace.expires_at is not None and workspace.expires_at < timezone.now():
        return None
    return workspace
