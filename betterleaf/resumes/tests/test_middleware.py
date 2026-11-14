from __future__ import annotations

from django.http import HttpResponse
from django.test import RequestFactory

from betterleaf.resumes.auth import create_guest_workspace
from betterleaf.resumes.middleware import WorkspaceMiddleware
from betterleaf.resumes.models import Workspace
from betterleaf.users.tests.factories import UserFactory


def _run(path: str, *, user=None, cookie: str | None = None):
    """Run the middleware; return the request.workspace the view would see."""
    request = RequestFactory().get(path)
    if user is not None:
        request.user = user
    if cookie is not None:
        request.COOKIES["bl_session"] = cookie
    seen = {}

    def view(req):
        seen["workspace"] = req.workspace
        return HttpResponse()

    WorkspaceMiddleware(view)(request)
    return seen["workspace"]


def test_guest_without_cookie_gets_none_and_nothing_is_created(db):
    assert _run("/api/workspace/") is None
    assert Workspace.objects.count() == 0


def test_guest_with_valid_cookie_gets_their_workspace(db):
    workspace, raw = create_guest_workspace()

    assert _run("/api/workspace/", cookie=raw) == workspace


def test_guest_with_unknown_cookie_gets_none(db):
    assert _run("/api/workspace/", cookie="bogus") is None
    assert Workspace.objects.count() == 0


def test_authenticated_user_gets_their_workspace_created_lazily(db):
    user = UserFactory.create()

    workspace = _run("/api/workspace/", user=user)

    assert workspace.user_id == user.id
    assert _run("/api/workspace/", user=user) == workspace
    assert Workspace.objects.count() == 1


def test_non_api_paths_get_no_workspace_and_no_queries(db, django_assert_num_queries):
    user = UserFactory.create()

    with django_assert_num_queries(0):
        assert _run("/accounts/login/", user=user) is None
