from __future__ import annotations

from unittest.mock import MagicMock

from betterleaf.users.adapters import SocialAccountAdapter


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
