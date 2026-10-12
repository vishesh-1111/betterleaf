from __future__ import annotations

from unittest.mock import MagicMock

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from betterleaf.users.adapters import AccountAdapter
from betterleaf.users.adapters import SocialAccountAdapter
from betterleaf.users.tests.factories import UserFactory


def _post_login(settings, adapter):
    request = RequestFactory().get("/accounts/google/login/callback/")
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    request.session.save()
    user = UserFactory.create()
    return adapter.post_login(
        request,
        user,
        email_verification="none",
        signal_kwargs={},
        email=user.email,
        signup=True,
        redirect_url=None,
    )


def test_post_login_clears_bl_session_cookie(settings, db):
    settings.FRONTEND_URL = "http://localhost:3000"
    adapter = AccountAdapter()

    response = _post_login(settings, adapter)

    assert response.status_code == 302
    assert response["Location"] == "http://localhost:3000/?download=true"
    # bl_session cookie is deleted (max-age/expires in the past or empty)
    assert "bl_session" in response.cookies
    assert response.cookies["bl_session"]["max-age"] == 0


def test_get_login_redirect_url(settings):
    settings.FRONTEND_URL = "http://localhost:3000"
    adapter = AccountAdapter()

    url = adapter.get_login_redirect_url(MagicMock())

    assert url == "http://localhost:3000/?download=true"


def test_get_login_redirect_url_strips_trailing_slash(settings):
    settings.FRONTEND_URL = "http://localhost:3000/"
    adapter = AccountAdapter()

    url = adapter.get_login_redirect_url(MagicMock())

    assert url == "http://localhost:3000/?download=true"


def test_get_signup_redirect_url(settings):
    settings.FRONTEND_URL = "http://localhost:3000"
    adapter = AccountAdapter()

    url = adapter.get_signup_redirect_url(MagicMock())

    assert url == "http://localhost:3000/?download=true"


def test_get_signup_redirect_url_strips_trailing_slash(settings):
    settings.FRONTEND_URL = "http://localhost:3000/"
    adapter = AccountAdapter()

    url = adapter.get_signup_redirect_url(MagicMock())

    assert url == "http://localhost:3000/?download=true"


def test_get_connect_redirect_url(settings):
    settings.FRONTEND_URL = "http://localhost:3000"
    adapter = SocialAccountAdapter()
    request = MagicMock()
    socialaccount = MagicMock()

    url = adapter.get_connect_redirect_url(request, socialaccount)

    assert url == "http://localhost:3000/?download=true"


def test_get_connect_redirect_url_strips_trailing_slash(settings):
    settings.FRONTEND_URL = "http://localhost:3000/"
    adapter = SocialAccountAdapter()

    url = adapter.get_connect_redirect_url(MagicMock(), MagicMock())

    assert url == "http://localhost:3000/?download=true"
