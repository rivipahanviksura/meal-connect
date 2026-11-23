from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api import auth, organization_application
from app.api.dependencies import get_active_user, get_current_organization
from app.db.models.user import UserRole
from app.db.session import get_db
from app.main import app
from app.schemas.organization_application import ApplicationSubmitted


@pytest.fixture
def api(monkeypatch):
    db = Mock()
    user = SimpleNamespace(user_id=1, role=UserRole.ngo_staff)
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)
    monkeypatch.setitem(app.dependency_overrides, get_active_user, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, get_current_organization, lambda: object())
    with TestClient(app) as client:
        yield client, db


def assert_validation_error(response, field):
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in {item["field"] for item in error["fields"]}


@pytest.mark.parametrize(("field", "value"), [
    ("first_name", "   "),
    ("last_name", "Invalid\x00name"),
    ("phone", "077\x00123456"),
    ("role", "admin"),
])
def test_registration_rejects_invalid_fields_before_hashing(api, monkeypatch, field, value):
    client, db = api
    hash_password = Mock()
    monkeypatch.setattr(auth, "hash_password", hash_password)

    response = client.post("/api/v1/auth/register", json={
        "first_name": "Test",
        "last_name": "Applicant",
        "email": "applicant@example.com",
        "account_type": "ngo",
        "password": "TestPassword123",
        field: value,
    })

    assert_validation_error(response, field)
    hash_password.assert_not_called()
    assert db.mock_calls == []


@pytest.mark.parametrize(("field", "value"), [
    ("city", "Colombo\x00"),
    ("available_before", "1763211600"),
    ("available_before", "0001-01-01T00:00:00+05:30"),
])
def test_browsing_validates_query_before_database_access(api, field, value):
    client, db = api

    response = client.get("/api/v1/donations", params={field: value})

    assert_validation_error(response, field)
    assert db.mock_calls == []


def test_application_rejects_invalid_draft_fields_before_persistence(api):
    client, db = api

    response = client.post("/api/v1/organization-applications", json={
        "organization_type": "ngo",
        "name": "NGO",
        "contact_email": "ngo@example.com",
        "address_line": "Main Street",
        "city": "Colombo",
        "representative_name": "Test Applicant",
        "operational_details": {"operating_area": "Colombo\x00"},
    })

    assert_validation_error(response, "ngo.operational_details.operating_area")
    assert db.mock_calls == []


@pytest.mark.parametrize("action", ["submit", "resubmit"])
def test_application_submission_rejects_unexpected_body_fields(api, monkeypatch, action):
    client, db = api
    submit = Mock()
    monkeypatch.setattr(organization_application, "submit_application", submit)

    response = client.post(
        f"/api/v1/organization-applications/2/{action}",
        json={"verification_status": "approved"},
    )

    assert_validation_error(response, "verification_status")
    submit.assert_not_called()
    assert db.mock_calls == []


@pytest.mark.parametrize("action", ["submit", "resubmit"])
@pytest.mark.parametrize("kwargs", [{}, {"json": {}}], ids=["no-body", "empty-object"])
def test_application_submission_preserves_supported_empty_bodies(api, monkeypatch, action, kwargs):
    client, db = api
    submit = Mock(return_value=ApplicationSubmitted(application_id=2, organization_id=2))
    monkeypatch.setattr(organization_application, "submit_application", submit)

    response = client.post(f"/api/v1/organization-applications/2/{action}", **kwargs)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending_verification"
    submit.assert_called_once_with(db, 1, 2, resubmitting=action == "resubmit")



def test_donation_edit_and_cancel_document_the_runtime_routes():
    paths = app.openapi()["paths"]
    edit = paths["/api/v1/donations/{donation_id}"]["patch"]
    cancel = paths["/api/v1/donations/{donation_id}/cancel"]["post"]

    assert edit["operationId"].startswith("edit_donation_")
    assert cancel["operationId"].startswith("cancel_donation_listing_")
    path_id = next(parameter for parameter in edit["parameters"] if parameter["in"] == "path")
    assert path_id["schema"]["exclusiveMinimum"] == 0
