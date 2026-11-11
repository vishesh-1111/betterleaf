from __future__ import annotations

from datetime import timedelta

import pytest
from allauth.account.signals import user_logged_in
from django.http import HttpRequest
from django.utils import timezone

from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.models import Workspace
from betterleaf.resumes.signals import claim_anonymous_workspace
from betterleaf.users.tests.factories import UserFactory


def _request_with_cookie(raw: str) -> HttpRequest:
    request = HttpRequest()
    request.COOKIES = {"bl_session": raw}
    return request


def _guest_workspace(**kwargs) -> tuple[Workspace, str]:
    raw, token_hash = new_anonymous_token()
    return Workspace.objects.create(anonymous_token_hash=token_hash, **kwargs), raw


def test_claim_attaches_anonymous_workspace_to_user(db):
    workspace, raw = _guest_workspace(expires_at=timezone.now() + timedelta(days=1))
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


def test_claim_expired_guest_workspace_is_noop(db):
    workspace, raw = _guest_workspace(expires_at=timezone.now() - timedelta(days=1))
    user = UserFactory.create()

    claim_anonymous_workspace(
        sender=object(), request=_request_with_cookie(raw), user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id is None


def test_claim_user_with_stale_cookie_keeps_their_workspace(db):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)

    claim_anonymous_workspace(
        sender=object(),
        request=_request_with_cookie("stale"),
        user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id == user.id
    assert Workspace.objects.count() == 1


def test_claim_when_user_already_has_workspace_hits_merge_placeholder(db):
    user = UserFactory.create()
    Workspace.objects.create(user=user)
    guest, raw = _guest_workspace()

    with pytest.raises(NotImplementedError):
        claim_anonymous_workspace(
            sender=object(), request=_request_with_cookie(raw), user=user,
        )

    guest.refresh_from_db()
    assert guest.user_id is None  # untouched until the merge is implemented


def test_user_logged_in_signal_dispatches_claim(db):
    workspace, raw = _guest_workspace()
    user = UserFactory.create()

    user_logged_in.send(
        sender=__name__,
        request=_request_with_cookie(raw),
        user=user,
    )

    workspace.refresh_from_db()
    assert workspace.user_id == user.id
