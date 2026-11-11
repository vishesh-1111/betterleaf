from __future__ import annotations

import typing

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from betterleaf.resumes.auth import claim_guest_workspace
from betterleaf.resumes.auth import get_guest_workspace

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


@receiver(user_logged_in)
def claim_anonymous_workspace(
    sender: object,
    request: HttpRequest,
    user: object,
    **kwargs: typing.Any,
) -> None:
    """Attach the guest workspace carried by the browser to the user who just
    logged in, so in-progress work isn't stranded behind the ``bl_session``
    cookie once requests resolve to the signed-in user's workspace.
    """
    guest = get_guest_workspace(request)
    if guest is not None:
        claim_guest_workspace(guest, user)
