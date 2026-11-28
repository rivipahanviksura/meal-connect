"""HTTP authorization and validation tests for organization document review."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.core.exception_handlers import APIException
from app.db.models.user import AccountStatus, UserRole
from app.db.session import get_db
from app.main import app


REVIEW_URL = "/api/v1/admin/organization-applications/10/documents/20/review"
VALID_NOTE = "Registration evidence has been reviewed and accepted."


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def authenticate_as(role: UserRole, account_status=AccountStatus.active):
    user = SimpleNamespace(
        user_id=5,
        role=role,
        account_status=account_status,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return user


def sample_review_response(status="approved"):
    return {
        "data": {
            "application_id": 10,
            "document_id": 20,
            "review_status": status,
            "reviewed_by_user_id": 5,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "review_note": VALID_NOTE,
        }
    }


def test_document_review_requires_authentication(client):
    response = client.post(
        REVIEW_URL,
        json={"decision": "approved", "review_note": VALID_NOTE},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_non_admin_cannot_review_document(client):
    authenticate_as(UserRole.business_staff)
    with patch("app.api.admin_verification.review_application_document") as service:
        response = client.post(
            REVIEW_URL,
            json={"decision": "approved", "review_note": VALID_NOTE},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    service.assert_not_called()


def test_inactive_admin_cannot_review_document(client):
    authenticate_as(UserRole.admin, account_status=AccountStatus.suspended)
    with patch("app.api.admin_verification.review_application_document") as service:
        response = client.post(
            REVIEW_URL,
            json={"decision": "approved", "review_note": VALID_NOTE},
        )
    assert response.status_code == 403
    service.assert_not_called()


def test_admin_can_approve_document_through_api(client):
    authenticate_as(UserRole.admin)
    with patch(
        "app.api.admin_verification.review_application_document",
        return_value=sample_review_response(),
    ) as service:
        response = client.post(
            REVIEW_URL,
            json={"decision": "approved", "review_note": VALID_NOTE},
        )
    assert response.status_code == 200
    assert response.json()["data"]["review_status"] == "approved"
    service.assert_called_once()
    assert service.call_args.kwargs["application_id"] == 10
    assert service.call_args.kwargs["document_id"] == 20
    assert service.call_args.kwargs["admin_id"] == 5
    assert service.call_args.kwargs["decision"] == "approved"
    assert service.call_args.kwargs["review_note"] == VALID_NOTE


def test_admin_can_reject_document_through_api(client):
    authenticate_as(UserRole.admin)
    with patch(
        "app.api.admin_verification.review_application_document",
        return_value=sample_review_response(status="rejected"),
    ) as service:
        response = client.post(
            REVIEW_URL,
            json={"decision": "rejected", "review_note": VALID_NOTE},
        )
    assert response.status_code == 200
    assert response.json()["data"]["review_status"] == "rejected"
    assert service.call_args.kwargs["decision"] == "rejected"


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": "suspended", "review_note": VALID_NOTE},
        {"decision": "approved", "review_note": "short"},
        {"decision": "approved", "review_note": VALID_NOTE, "admin_id": 99},
    ],
)
def test_invalid_document_review_request_returns_422(client, payload):
    authenticate_as(UserRole.admin)
    with patch("app.api.admin_verification.review_application_document") as service:
        response = client.post(REVIEW_URL, json=payload)
    assert response.status_code == 422
    service.assert_not_called()


def test_missing_document_returns_404(client):
    authenticate_as(UserRole.admin)
    with patch(
        "app.api.admin_verification.review_application_document",
        side_effect=APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Document not found.",
        ),
    ):
        response = client.post(
            REVIEW_URL,
            json={"decision": "approved", "review_note": VALID_NOTE},
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_already_reviewed_document_returns_409(client):
    authenticate_as(UserRole.admin)
    with patch(
        "app.api.admin_verification.review_application_document",
        side_effect=APIException(
            status_code=409,
            code="DOCUMENT_ALREADY_REVIEWED",
            message="Document has already been reviewed.",
        ),
    ):
        response = client.post(
            REVIEW_URL,
            json={"decision": "rejected", "review_note": VALID_NOTE},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DOCUMENT_ALREADY_REVIEWED"
