"""Workspace identity: who is making this request?

A request is identified by exactly one ``Workspace``:

* a signed-in user owns one workspace (``Workspace.user``), created lazily;
* a guest is identified only by an anonymous workspace, named by the httpOnly
  ``bl_session`` cookie (stored hashed, expires after ``ANONYMOUS_WORKSPACE_TTL``).

On login the guest workspace is attached to the user (``claim_guest_workspace``).
"""

import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from betterleaf.resumes.models import Workspace

GUEST_COOKIE_NAME = "bl_session"
ANONYMOUS_WORKSPACE_TTL = timedelta(days=30)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_anonymous_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def set_workspace_cookie(response, raw: str) -> None:
    response.set_cookie(
        GUEST_COOKIE_NAME,
        raw,
        max_age=int(ANONYMOUS_WORKSPACE_TTL.total_seconds()),
        httponly=True,
        samesite="Lax",
    )


def delete_workspace_cookie(response) -> None:
    response.delete_cookie(GUEST_COOKIE_NAME)


def _authenticated_user(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return None


def get_guest_workspace(request) -> Workspace | None:
    """The unexpired anonymous workspace named by the `bl_session` cookie."""
    raw = request.COOKIES.get(GUEST_COOKIE_NAME)
    if not raw:
        return None
    workspace = Workspace.objects.filter(anonymous_token_hash=hash_token(raw)).first()
    if workspace is None:
        return None
    if workspace.expires_at is not None and workspace.expires_at < timezone.now():
        return None
    return workspace


def get_workspace(request) -> Workspace | None:
    """Resolve the request's workspace: the signed-in user's (created lazily),
    else the guest workspace named by the `bl_session` cookie."""
    user = _authenticated_user(request)
    if user is not None:
        workspace, _ = Workspace.objects.get_or_create(user=user)
        return workspace
    return get_guest_workspace(request)


def get_or_create_workspace(request) -> tuple[Workspace, str | None]:
    """Like `get_workspace`, but mints a guest workspace when there is none.

    Returns ``(workspace, raw_token)``; ``raw_token`` is set only when a new guest
    workspace was created, and must be handed to the client via
    ``set_workspace_cookie``.
    """
    workspace = get_workspace(request)
    if workspace is not None:
        return workspace, None

    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() + ANONYMOUS_WORKSPACE_TTL,
    )
    return workspace, raw


def claim_guest_workspace(guest: Workspace, user) -> None:
    """Attach a guest workspace to the user that just logged in."""
    existing = Workspace.objects.filter(user=user).first()
    if existing is not None:
        merge_guest_workspace(guest, existing)
        return
    guest.user = user
    guest.anonymous_token_hash = None
    guest.expires_at = None
    guest.save(update_fields=["user", "anonymous_token_hash", "expires_at"])


def merge_guest_workspace(guest: Workspace, existing: Workspace) -> None:
    """Fold a guest workspace into a user's already-existing workspace.

    Reached when a user who already owns a workspace logs in from a browser that
    holds a (valid) guest workspace.
    """
    msg = "merge_guest_workspace: not implemented yet"
    raise NotImplementedError(msg)
