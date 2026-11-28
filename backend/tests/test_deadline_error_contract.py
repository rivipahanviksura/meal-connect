from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers
from app.core.timezone import to_utc
from app.services.donation_availability import DonationExpiredError


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/naive-timestamp")
    def naive_timestamp():
        to_utc(
            datetime(2026, 11, 15, 18, 0),
            field_name="pickup_deadline",
        )
        return {"ok": True}

    @app.get("/expired-donation")
    def expired_donation():
        raise DonationExpiredError()

    return app


def test_naive_timestamp_returns_meal62_validation_envelope():
    response = TestClient(create_test_app()).get("/naive-timestamp")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["fields"][0]["field"] == "pickup_deadline"
    assert body["error"]["fields"][0]["code"] == "timezone_required"
    assert "details" not in body["error"]
    assert "request_id" not in body["error"]


def test_expired_donation_returns_meal62_conflict_envelope():
    response = TestClient(create_test_app()).get("/expired-donation")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "DONATION_EXPIRED"
    assert body["error"]["message"] == (
        DonationExpiredError.DEFAULT_MESSAGE
    )
    assert body["error"]["fields"] == []
    assert "details" not in body["error"]
    assert "request_id" not in body["error"]
