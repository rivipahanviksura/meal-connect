import pytest
from pydantic import ValidationError

from app.schemas.donation import DonationCreate


def valid_donation_data():
    return {
        "title": "Fresh Vegetables",
        "category": "Vegetables",
        "description": "Fresh surplus vegetables",
        "total_quantity": "25.50",
        "quantity_unit": "kg",
        "allergen_info": None,
        "storage_instructions": "Keep refrigerated",
        "prepared_at": "2026-11-15T08:00:00+05:30",
        "available_from": "2026-11-15T09:00:00+05:30",
        "pickup_deadline": "2026-11-15T17:00:00+05:30",
        "pickup_address": "Main Street",
        "pickup_city": "Colombo",
    }


def test_valid_donation_data_is_accepted():
    donation = DonationCreate(**valid_donation_data())

    assert donation.title == "Fresh Vegetables"
    assert donation.total_quantity == 25.50


def test_zero_quantity_is_rejected():
    data = valid_donation_data()
    data["total_quantity"] = "0"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_negative_quantity_is_rejected():
    data = valid_donation_data()
    data["total_quantity"] = "-5"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_deadline_before_available_from_is_rejected():
    data = valid_donation_data()
    data["pickup_deadline"] = "2026-11-15T08:30:00+05:30"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_prepared_at_after_deadline_is_rejected():
    data = valid_donation_data()
    data["prepared_at"] = "2026-11-15T18:00:00+05:30"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_client_cannot_supply_organization_id():
    data = valid_donation_data()
    data["organization_id"] = 10

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_client_cannot_supply_status():
    data = valid_donation_data()
    data["status"] = "available"

    with pytest.raises(ValidationError):
        DonationCreate(**data)
