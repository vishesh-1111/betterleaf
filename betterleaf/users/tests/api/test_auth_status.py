from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.test import APIRequestFactory

from betterleaf.users.api.views import auth_status

if TYPE_CHECKING:
    from betterleaf.users.models import User


@pytest.fixture
def api_rf() -> APIRequestFactory:
    return APIRequestFactory()


def test_auth_status_anonymous(api_rf: APIRequestFactory):
    request = api_rf.get("/api/users/auth-status/")
    request.user = AnonymousUser()

    response = auth_status(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"authenticated": False}


def test_auth_status_authenticated(user: User, api_rf: APIRequestFactory):
    request = api_rf.get("/api/users/auth-status/")
    request.user = user

    response = auth_status(request)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"authenticated": True}
