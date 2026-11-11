from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone

from betterleaf.resumes.auth import get_guest_workspace
from betterleaf.resumes.auth import get_or_create_workspace
from betterleaf.resumes.auth import get_workspace
from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.models import Workspace
from betterleaf.users.tests.factories import UserFactory


def _guest_request(raw: str | None = None) -> HttpRequest:
    request = HttpRequest()
    request.COOKIES = {} if raw is None else {"bl_session": raw}
    return request


def _user_request(user) -> HttpRequest:
    request = HttpRequest()
    request.user = user
    return request


def test_get_guest_workspace_valid_cookie(db):
    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() + timedelta(days=1),
    )

    assert get_guest_workspace(_guest_request(raw)) == workspace


def test_get_guest_workspace_no_unknown_or_expired_cookie(db):
    raw, token_hash = new_anonymous_token()
    Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    assert get_guest_workspace(_guest_request()) is None
    assert get_guest_workspace(_guest_request("unknown")) is None
    assert get_guest_workspace(_guest_request(raw)) is None


def test_get_workspace_guest_without_cookie_is_none_and_creates_nothing(db):
    assert get_workspace(_guest_request()) is None
    assert Workspace.objects.count() == 0


def test_get_workspace_creates_user_workspace_once(db):
    user = UserFactory.create()

    first = get_workspace(_user_request(user))
    second = get_workspace(_user_request(user))

    assert first == second
    assert Workspace.objects.filter(user=user).count() == 1


def test_get_or_create_workspace_guest_mints_token_only_when_creating(db):
    workspace, raw = get_or_create_workspace(_guest_request())
    assert raw is not None
    assert workspace.user_id is None
    assert workspace.expires_at is not None

    again, raw_again = get_or_create_workspace(_guest_request(raw))
    assert again == workspace
    assert raw_again is None


def test_get_or_create_workspace_user_never_mints_token(db):
    user = UserFactory.create()

    workspace, raw = get_or_create_workspace(_user_request(user))

    assert raw is None
    assert workspace.user_id == user.id
