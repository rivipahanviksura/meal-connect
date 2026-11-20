
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.db.models.user import UserRole, AccountStatus
from app.core.exception_handlers import APIException
from app.schemas.admin_verification import (
    AdminDecisionData,
    AdminDecisionResponse,
)


DECISION_URL = (
    "/api/v1/admin/organization-applications/10/decision"
)


@pytest.fixture
def client():
    app.dependency_overrides.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def override_user(role=UserRole.admin):
    user = SimpleNamespace(
        user_id=5,
        role=role,
        account_status=AccountStatus.active,
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()

    return user


def make_decision_response(action, status):
    return AdminDecisionResponse(
        data=AdminDecisionData(
            application_id=10,
            organization_id=10,
            action=action,
            status=status,
            reviewed_by_user_id=5,
            reviewed_at=datetime.now(timezone.utc),
            reason="Registration evidence has been reviewed.",
        )
    )


def test_admin_can_reject_through_api(client):
    override_user(UserRole.admin)

    expected = make_decision_response(
        action="reject",
        status="rejected",
    )

    with patch(
        "app.api.admin_verification.reject_application",
        return_value=expected,
    ) as mocked_service:
        response = client.post(
            DECISION_URL,
            json={
                "decision": "rejected",
                "review_note": "Registration evidence is incomplete.",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["action"] == "reject"

    mocked_service.assert_called_once()
    assert mocked_service.call_args.kwargs["admin_id"] == 5


def test_non_admin_cannot_make_decision(client):
    override_user(UserRole.business_staff)

    response = client.post(
        DECISION_URL,
        json={
            "decision": "rejected",
            "review_note": "Registration evidence is incomplete.",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_request_corrections_through_api(client):
    override_user(UserRole.admin)

    expected = make_decision_response(
        action="request_corrections",
        status="rejected",
    )

    with patch(
        "app.api.admin_verification.request_application_corrections",
        return_value=expected,
    ) as mocked_service:
        response = client.post(
            DECISION_URL,
            json={
                "decision": "request_corrections",
                "review_note": "Please upload updated registration evidence.",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["action"] == "request_corrections"
    mocked_service.assert_called_once()


def test_admin_receives_not_found_error(client):
    override_user(UserRole.admin)

    with patch(
        "app.api.admin_verification.reject_application",
        side_effect=APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Application not found.",
        ),
    ):
        response = client.post(
            DECISION_URL,
            json={
                "decision": "rejected",
                "review_note": "Registration evidence is incomplete.",
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_admin_invalid_decision_returns_422(client):
    override_user(UserRole.admin)

    response = client.post(
        DECISION_URL,
        json={
            "decision": "suspended",
            "review_note": "Registration evidence reviewed.",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
