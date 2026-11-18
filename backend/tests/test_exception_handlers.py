
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers


def create_test_client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test-unauthorized")
    def unauthorized():
        raise HTTPException(status_code=401, detail="Not authenticated")

    @app.get("/test-forbidden")
    def forbidden():
        raise HTTPException(status_code=403, detail="Permission denied")

    return TestClient(app)


def test_unauthenticated_error_format():
    client = create_test_client()

    response = client.get("/test-unauthorized")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "AUTH_REQUIRED",
            "message": "Authentication required",
            "fields": [],
        }
    }


def test_forbidden_error_format():
    client = create_test_client()

    response = client.get("/test-forbidden")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "FORBIDDEN",
            "message": "Permission denied",
            "fields": [],
        }
    }

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers


@pytest.fixture
def error_client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test-404")
    def test_404_route():
        raise HTTPException(
            status_code=404,
            detail="Resource does not exist",
        )

    @app.get("/test-409/{error_code}")
    def test_409_route(error_code: str):
        raise HTTPException(
            status_code=409,
            detail=error_code,
        )

    return TestClient(app)


def test_404_not_found_response(error_client):
    response = error_client.get("/test-404")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
            "fields": [],
        }
    }


@pytest.mark.parametrize(
    "error_code",
    [
        "QUANTITY_CONFLICT",
        "DONATION_EXPIRED",
        "ALREADY_EXISTS",
        "INVALID_STATE_TRANSITION",
    ],
)
def test_409_preserves_specific_error_code(
    error_client,
    error_code,
):
    response = error_client.get(
        f"/test-409/{error_code}"
    )

    assert response.status_code == 409

    assert response.json()["error"]["code"] == error_code
    assert response.json()["error"]["fields"] == []
