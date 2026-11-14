import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers
from app.schemas.user import LoginResponse, RegistrationRequest
from app.schemas.common import ErrorResponse


validation_app = FastAPI()
register_exception_handlers(validation_app)


@validation_app.post("/test/users")
def create_test_user(payload: RegistrationRequest):
    return {"message": "Valid payload"}

client = TestClient(validation_app)


def test_invalid_email_returns_422():
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "last_name": "User",
            "email": "invalid-email",
            "password": "ExamplePassword123!",
            "account_type": "ngo"
        },
    )

    assert response.status_code == 422

    body = ErrorResponse.model_validate(response.json())
    assert body.error.code == "VALIDATION_ERROR"
    assert any(
        field.field == "email"
        for field in body.error.fields
    )


def test_missing_required_field_returns_422():
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "email": "demo@example.com",
            "password": "ExamplePassword123!",
            "account_type": "ngo"
        },
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert any(f["field"] == "last_name" for f in fields)


def test_short_password_is_rejected_without_echo():
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo@example.com",
            "password": "abc",
            "account_type": "ngo"
        },
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert any(f["field"] == "password" for f in fields)
    assert '"input"' not in response.text
    assert '"ctx"' not in response.text


def test_extra_fields_are_rejected():
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo@example.com",
            "password": "ExamplePassword123!",
            "role": "admin",
            "account_type": "ngo"
        },
    )

    assert response.status_code == 422
    fields = response.json()["error"]["fields"]
    assert any(f["field"] == "role" for f in fields)


@pytest.mark.parametrize("account_type", ["business", "ngo"])
def test_valid_payload_is_accepted(account_type):
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo@example.com",
            "password": "ExamplePassword123!",
            "account_type": account_type,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Valid payload"}

@pytest.mark.parametrize(
    "account_type_fields",
    [{"account_type": "volunteer"}, {"account_type": "admin"}, {}],
    ids=["volunteer", "admin", "missing"],
)
def test_invalid_or_missing_account_type_returns_422(account_type_fields):
    response = client.post(
        "/test/users",
        json={
            "first_name": "Demo",
            "last_name": "User",
            "email": "demo@example.com",
            "password": "ExamplePassword123!",
            **account_type_fields,
        },
    )

    assert response.status_code == 422

    body = ErrorResponse.model_validate(response.json())
    assert body.error.code == "VALIDATION_ERROR"
    assert any(field.field == "account_type" for field in body.error.fields)

def test_login_response_matches_frontend_contract():
    response = LoginResponse(
        data=LoginResponse.Data(
            access_token="test-access-token",
            expires_in=1800,
            user={
                "user_id": 1,
                "email": "demo@example.com",
                "role": "ngo_staff",
            },
        )
    )

    assert response.model_dump(mode="json") == {
        "data": {
            "access_token": "test-access-token",
            "token_type": "bearer",
            "expires_in": 1800,
            "user": {
                "user_id": 1,
                "email": "demo@example.com",
                "role": "ngo_staff",
            },
        },
    }
