import pytest
from rest_framework.test import APIClient

from betterleaf.resumes.models import Resume
from betterleaf.resumes.models import Workspace
from betterleaf.users.tests.factories import UserFactory

DATA = {
    "name": "Jane Doe",
    "contact": {"email": "jane@example.com"},
    "experience": [
        {
            "id": "exp1",
            "company": "Acme",
            "role": "Engineer",
            "duration": "2020 - 2022",
            "bullets": [{"id": "b1", "text": "Built REST APIs in Python"}],
        },
    ],
    "section_order": ["experience"],
}


@pytest.fixture
def client_and_resume(db):
    user = UserFactory.create()
    workspace = Workspace.objects.create(user=user)
    resume = Resume.objects.create(
        workspace=workspace, title="cv", template="jakes", main_tex="old",
    )
    client = APIClient()
    client.force_login(user)
    return client, resume


def test_patch_data_rerenders_latex(client_and_resume):
    client, resume = client_and_resume
    res = client.patch(
        f"/api/resumes/{resume.id}/", {"structured_data": DATA}, format="json",
    )
    assert res.status_code == 200
    assert "Built REST APIs in Python" in res.data["main_tex"]
    assert "Jane Doe" in res.data["main_tex"]
    resume.refresh_from_db()
    assert resume.structured_data["experience"][0]["bullets"][0]["id"] == "b1"
    assert resume.main_tex == res.data["main_tex"]


def test_data_wins_over_main_tex_in_same_request(client_and_resume):
    client, resume = client_and_resume
    res = client.patch(
        f"/api/resumes/{resume.id}/",
        {"structured_data": DATA, "main_tex": "hand written"},
        format="json",
    )
    assert res.status_code == 200
    assert res.data["main_tex"] != "hand written"


def test_missing_ids_are_filled(client_and_resume):
    client, resume = client_and_resume
    data = {"name": "Jane", "projects": [{"title": "P", "bullets": ["did a thing"]}]}
    res = client.patch(
        f"/api/resumes/{resume.id}/", {"structured_data": data}, format="json",
    )
    assert res.status_code == 200
    project = res.data["structured_data"]["projects"][0]
    assert project["id"]
    assert project["bullets"][0]["id"]


def test_invalid_data_changes_nothing(client_and_resume):
    client, resume = client_and_resume
    res = client.patch(
        f"/api/resumes/{resume.id}/",
        {"structured_data": {"experience": "nope"}},
        format="json",
    )
    assert res.status_code == 400
    resume.refresh_from_db()
    assert resume.main_tex == "old"
    assert resume.structured_data == {}


def test_main_tex_only_patch_still_works(client_and_resume):
    client, resume = client_and_resume
    res = client.patch(
        f"/api/resumes/{resume.id}/", {"main_tex": "new"}, format="json",
    )
    assert res.status_code == 200
    resume.refresh_from_db()
    assert resume.main_tex == "new"


def test_workspace_payload_includes_data(client_and_resume):
    client, resume = client_and_resume
    resume.structured_data = DATA
    resume.save()
    res = client.get("/api/workspace/")
    assert res.status_code == 200
    assert res.data["resumes"][0]["structured_data"]["name"] == "Jane Doe"
