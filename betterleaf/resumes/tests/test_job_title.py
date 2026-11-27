from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from betterleaf.resumes.models import Workspace
from betterleaf.resumes.services.llm import LLMError
from betterleaf.resumes.services.llm import LLMUnavailableError
from betterleaf.users.tests.factories import UserFactory

LLM = "betterleaf.resumes.services.job_title.post_deepseek_chat"
URL = "/api/job-title/"


@pytest.fixture
def client(db):
    user = UserFactory()
    Workspace.objects.create(user=user)
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_returns_cleaned_title(client):
    with patch(LLM, return_value={"title": "  Senior   Backend Engineer "}):
        res = client.post(URL, {"job_text": "We are hiring..."}, format="json")
    assert res.status_code == 200
    assert res.data == {"title": "Senior Backend Engineer"}


def test_requires_job_text(client):
    assert client.post(URL, {"job_text": " "}, format="json").status_code == 400


def test_bad_output_is_502(client):
    with patch(LLM, return_value={"title": ""}):
        assert client.post(URL, {"job_text": "x"}, format="json").status_code == 502


def test_llm_outage_is_503(client):
    with patch(LLM, side_effect=LLMUnavailableError("down")):
        assert client.post(URL, {"job_text": "x"}, format="json").status_code == 503


def test_llm_error_is_502(client):
    with patch(LLM, side_effect=LLMError("bad")):
        assert client.post(URL, {"job_text": "x"}, format="json").status_code == 502
