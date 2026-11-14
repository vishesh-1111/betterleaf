from __future__ import annotations

from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone

from betterleaf.resumes.auth import create_guest_workspace
from betterleaf.resumes.auth import get_guest_workspace
from betterleaf.resumes.auth import get_or_create_workspace
from betterleaf.resumes.auth import get_user_workspace
from betterleaf.resumes.auth import hash_token
from betterleaf.resumes.auth import new_anonymous_token
from betterleaf.resumes.auth import resolve_workspace
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


def test_get_guest_workspace_valid_token(db):
    raw, token_hash = new_anonymous_token()
    workspace = Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() + timedelta(days=1),
    )

    assert get_guest_workspace(raw) == workspace


def test_get_guest_workspace_no_unknown_or_expired_token(db):
    raw, token_hash = new_anonymous_token()
    Workspace.objects.create(
        anonymous_token_hash=token_hash,
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    assert get_guest_workspace(None) is None
    assert get_guest_workspace("unknown") is None
    assert get_guest_workspace(raw) is None


def test_get_user_workspace_creates_it_once(db):
    user = UserFactory.create()

    first = get_user_workspace(user)
    second = get_user_workspace(user)

    assert first == second
    assert Workspace.objects.filter(user=user).count() == 1


def test_create_guest_workspace_stores_only_the_token_hash(db):
    workspace, raw = create_guest_workspace()

    assert workspace.user_id is None
    assert workspace.expires_at is not None
    assert workspace.anonymous_token_hash == hash_token(raw)
    assert raw != workspace.anonymous_token_hash


def test_resolve_workspace_guest_without_cookie_is_none_and_creates_nothing(db):
    assert resolve_workspace(_guest_request()) is None
    assert Workspace.objects.count() == 0


def test_resolve_workspace_guest_with_cookie(db):
    workspace, raw = create_guest_workspace()

    assert resolve_workspace(_guest_request(raw)) == workspace


def test_resolve_workspace_user_wins_over_guest_cookie(db):
    user = UserFactory.create()
    _, raw = create_guest_workspace()
    request = _user_request(user)
    request.COOKIES = {"bl_session": raw}

    assert resolve_workspace(request) == get_user_workspace(user)


def test_get_or_create_workspace_mints_token_only_when_creating(db):
    request = _guest_request()
    request.workspace = None
    workspace, raw = get_or_create_workspace(request)
    assert raw is not None
    assert workspace.user_id is None

    request.workspace = workspace
    again, raw_again = get_or_create_workspace(request)
    assert again == workspace
    assert raw_again is None
    assert Workspace.objects.count() == 1
