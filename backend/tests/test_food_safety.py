
import pytest
from fastapi.testclient import TestClient

from app.core.food_safety import (
    FOOD_SAFETY_GUIDANCE,
    get_food_safety_guidance,
)
from app.main import app


def test_donation_creation_guidance():
    result = get_food_safety_guidance(
        "donation_creation"
    )

    assert result["title"] == "Food Safety Notice"
    assert "safe consumption" in result["message"]


def test_donation_details_guidance():
    result = get_food_safety_guidance(
        "donation_details"
    )

    assert "allergen" in result["message"]


def test_pickup_guidance():
    result = get_food_safety_guidance("pickup")

    assert "storage" in result["message"]


def test_platform_does_not_claim_certification():
    for item in FOOD_SAFETY_GUIDANCE.values():
        message = item["message"].lower()

        assert "does not" in message
        assert "food safety" in message


def test_invalid_location():
    with pytest.raises(ValueError):
        get_food_safety_guidance("invalid")


@pytest.mark.parametrize(
    ("location", "title", "message_text"),
    [
        ("donation_creation", "Food Safety Notice", "suitable for safe consumption"),
        ("donation_details", "Food Safety Reminder", "allergen information"),
        ("pickup", "Safe Food Collection", "handling and storage instructions"),
    ],
)
def test_food_safety_guidance_endpoint(location, title, message_text):
    with TestClient(app) as client:
        response = client.get(f"/api/v1/food-safety/{location}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == title
    assert message_text in body["message"]


def test_food_safety_unknown_location_returns_standard_error():
    with TestClient(app) as client:
        response = client.get("/api/v1/food-safety/unknown")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Guidance not found",
            "fields": [],
        },
    }
