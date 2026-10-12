from __future__ import annotations

from allauth.account.signals import user_logged_in
from django.http import HttpRequest

from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.signals import claim_anonymous_workspace
from betterleaf.users.tests.factories import UserFactory


def _request_with_cookie(raw: str) -> HttpRequest:
    request = HttpRequest()
    request.COOKIES = {"bl_session": raw}
    return request


def test_claim_attaches_anonymous_workspace_to_user(db):
    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(anonymous_token_hash=token_hash)
    user = UserFactory.create()

    claim_anonymous_workspace(
        sender=object(), request=_request_with_cookie(raw), user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id == user.id
    assert workspace.anonymous_token_hash is None
    assert workspace.expires_at is None


def test_claim_no_cookie_is_noop(db):
    user = UserFactory.create()

    claim_anonymous_workspace(
        sender=object(), request=HttpRequest(), user=user,
    )

    assert Workspace.objects.count() == 0


def test_claim_unknown_cookie_is_noop(db):
    user = UserFactory.create()

    claim_anonymous_workspace(
        sender=object(),
        request=_request_with_cookie("bogus-token"),
        user=user,
    )

    assert Workspace.objects.count() == 0


def test_claim_already_claimed_is_noop(db):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)

    claim_anonymous_workspace(
        sender=object(),
        request=_request_with_cookie("stale"),
        user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id == user.id


def test_user_logged_in_signal_dispatches_claim(db):
    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(anonymous_token_hash=token_hash)
    user = UserFactory.create()

    user_logged_in.send(
        sender=__name__,
        request=_request_with_cookie(raw),
        user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id == user.id
