
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exception_handlers import (
    APIException,
    register_exception_handlers,
)


app = FastAPI()
register_exception_handlers(app)


@app.get("/test/unauthorized")
def unauthorized():
    raise APIException(
        status_code=401,
        code="AUTH_REQUIRED",
        message="Authentication is required.",
    )


@app.get("/test/forbidden")
def forbidden():
    raise APIException(
        status_code=403,
        code="FORBIDDEN",
        message="You do not have permission.",
    )


client = TestClient(app)


def test_unauthorized_returns_401():
    response = client.get("/test/unauthorized")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "AUTH_REQUIRED",
            "message": "Authentication is required.",
            "fields": [],
        }
    }


def test_forbidden_returns_403():
    response = client.get("/test/forbidden")

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "FORBIDDEN",
            "message": "You do not have permission.",
            "fields": [],
        }
    }
