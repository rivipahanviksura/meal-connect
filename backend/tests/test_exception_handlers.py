
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
