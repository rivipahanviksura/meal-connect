
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

URL = "/api/v1/admin/organization-applications/1/reject"


def test_reject_requires_authentication():
    response = client.post(
        URL,
        json={
            "reason": "Missing required registration documents"
        },
    )

    assert response.status_code == 401

    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"


def test_reject_requires_reason():
    # Request validation should reject an invalid body.
    # This test checks the Pydantic schema directly.
    from pydantic import ValidationError
    import pytest

    from app.schemas.admin_verification import AdminRejectRequest

    with pytest.raises(ValidationError):
        AdminRejectRequest(reason="")


def test_reject_does_not_accept_admin_id():
    from pydantic import ValidationError
    import pytest

    from app.schemas.admin_verification import AdminRejectRequest

    with pytest.raises(ValidationError):
        AdminRejectRequest(
            reason="Missing registration documents",
            reviewed_by_user_id=999,
        )

CORRECTION_URL = (
    "/api/v1/admin/organization-applications/"
    "1/request-corrections"
)


def test_corrections_require_authentication():
    response = client.post(
        CORRECTION_URL,
        json={
            "reason": "Please upload the required registration evidence."
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_corrections_reject_empty_reason_without_token():
    response = client.post(
        CORRECTION_URL,
        json={"reason": ""},
    )

    # Depending on dependency evaluation, an unauthenticated
    # request may fail authentication before body validation.
    assert response.status_code in (401, 422)


def test_corrections_reject_client_identity_override():
    from pydantic import ValidationError
    import pytest

    from app.schemas.admin_verification import AdminCorrectionRequest

    with pytest.raises(ValidationError):
        AdminCorrectionRequest(
            reason="Please provide missing organization documents.",
            reviewed_by_user_id=999,
        )


from pydantic import ValidationError
import pytest

from app.schemas.admin_verification import AdminDecisionRequest


DECISION_URL = (
    "/api/v1/admin/organization-applications/1/decision"
)


def test_decision_requires_authentication():
    response = client.post(
        DECISION_URL,
        json={
            "decision": "rejected",
            "review_note": "Registration evidence is incomplete.",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_decision_rejects_invalid_action():
    with pytest.raises(ValidationError):
        AdminDecisionRequest(
            decision="suspended",
            review_note="Registration evidence reviewed.",
        )


def test_decision_requires_review_note():
    with pytest.raises(ValidationError):
        AdminDecisionRequest(
            decision="rejected",
            review_note="",
        )


def test_decision_rejects_client_role_override():
    with pytest.raises(ValidationError):
        AdminDecisionRequest(
            decision="approved",
            review_note="Registration evidence reviewed and accepted.",
            role="admin",
        )


def test_valid_decision_schema():
    request = AdminDecisionRequest(
        decision="rejected",
        review_note="Registration evidence is incomplete.",
    )

    assert request.decision == "rejected"
    assert request.review_note == "Registration evidence is incomplete."
