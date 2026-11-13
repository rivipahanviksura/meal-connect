
import pytest

from app.core.food_safety import (
    FOOD_SAFETY_GUIDANCE,
    get_food_safety_guidance,
)


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
