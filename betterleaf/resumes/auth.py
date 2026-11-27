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

from django.conf import settings
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
        # Shared across app./api. subdomains so the frontend's server-side
        # routing gate (proxy.ts) receives it. None => host-only (local dev).
        domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None),
        secure=getattr(settings, "SESSION_COOKIE_SECURE", False),
    )


def delete_workspace_cookie(response) -> None:
    response.delete_cookie(
        GUEST_COOKIE_NAME,
        domain=getattr(settings, "SESSION_COOKIE_DOMAIN", None),
    )


def get_user_workspace(user) -> Workspace:
    """The signed-in user's workspace, created lazily on first use."""
    workspace, _ = Workspace.objects.get_or_create(user=user)
    return workspace


def get_guest_workspace(raw_token: str | None) -> Workspace | None:
    """The unexpired anonymous workspace named by a ``bl_session`` token."""
    if not raw_token:
        return None
    workspace = Workspace.objects.filter(
        anonymous_token_hash=hash_token(raw_token),
    ).first()
    if workspace is None:
        return None
    if workspace.expires_at is not None and workspace.expires_at < timezone.now():
        return None
    return workspace


def create_guest_workspace() -> tuple[Workspace, str]:
    """Mint an anonymous workspace.

    Returns ``(workspace, raw_token)``; the raw token must be handed to the
    client via ``set_workspace_cookie`` (only its hash is stored).
    """
    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() + ANONYMOUS_WORKSPACE_TTL,
    )
    return workspace, raw


def resolve_workspace(request) -> Workspace | None:
    """Who is this request? The signed-in user's workspace, else the guest
    workspace named by the cookie, else ``None``. Never creates a guest
    workspace; that is ``get_or_create_workspace``'s job.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return get_user_workspace(user)
    return get_guest_workspace(request.COOKIES.get(GUEST_COOKIE_NAME))


def get_or_create_workspace(request) -> tuple[Workspace, str | None]:
    """The workspace service for flows that must have one (the upload).

    Relies on ``WorkspaceMiddleware`` having set ``request.workspace``. Returns
    ``(workspace, raw_token)``; ``raw_token`` is set only when a new guest
    workspace was created, and the caller must set it with
    ``set_workspace_cookie``.
    """
    workspace = request.workspace
    if workspace is not None:
        return workspace, None
    return create_guest_workspace()


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
