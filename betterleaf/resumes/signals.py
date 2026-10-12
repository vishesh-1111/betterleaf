from __future__ import annotations

import typing

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from betterleaf.resumes.auth import hash_token
from betterleaf.resumes.models import Workspace

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


@receiver(user_logged_in)
def claim_anonymous_workspace(
    sender: object,
    request: HttpRequest,
    user: object,
    **kwargs: typing.Any,
) -> None:
    """Attach the logged-in user's anonymous workspace to their account.

    Before login the frontend works against an anonymous workspace named by the
    ``bl_session`` httpOnly cookie. After a Google login ``get_workspace``
    resolves to the authenticated branch and ignores that cookie, so the user's
    in-progress resume would be stranded in the anonymous workspace and later
    requests 403. Claim it here: attach it to the user and clear the anonymous
    token/expiry so the authenticated branch resolves to the same workspace.
    """
    raw = request.COOKIES.get("bl_session")
    if not raw:
        return
    try:
        workspace = Workspace.objects.get(anonymous_token_hash=hash_token(raw))
    except Workspace.DoesNotExist:
        return
    if workspace.user_id is not None:
        return  # already claimed; nothing to do
    workspace.user = user
    workspace.anonymous_token_hash = None
    workspace.expires_at = None
    workspace.save(update_fields=["user", "anonymous_token_hash", "expires_at"])
