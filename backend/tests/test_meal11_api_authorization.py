
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.dependencies import get_active_user

from app.main import app
from app.db.session import get_db
from app.core.config import settings


def fake_get_db():
    yield None


@pytest.fixture
def client(monkeypatch):
    # Test-only JWT secret key
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("meal11-test-only-secret-key-1234567890")
    )

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_application_requires_authentication(client):
    response = client.get(
        "/api/v1/organization-applications/me"
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_application_rejects_invalid_token(client):
    response = client.get(
        "/api/v1/organization-applications/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_cannot_submit_another_users_application(monkeypatch):
    # Simulate an authenticated user
    current_user = SimpleNamespace(user_id=10)

    # Mock the database
    db = MagicMock()
    db.get.return_value = current_user

    # No application belongs to this user
    db.scalar.return_value = None

    # Keep real ownership query, bypass unrelated applicant checks
    monkeypatch.setattr(
        "app.services.application_submission.require_applicant",
        lambda user: user,
    )

    app.dependency_overrides[get_active_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/v1/organization-applications/20/submit"
            )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

        # Verify that the database query checks both
        # application ID and authenticated user ID.
        db.scalar.assert_called_once()

        query = db.scalar.call_args.args[0]
        parameters = query.compile().params

        assert 20 in parameters.values()
        assert 10 in parameters.values()

    finally:
        app.dependency_overrides.pop(get_active_user, None)
        app.dependency_overrides.pop(get_db, None)

