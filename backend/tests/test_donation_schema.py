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


def test_client_can_supply_organization_id_for_membership_check():
    data = valid_donation_data()
    data["organization_id"] = 10

    assert DonationCreate(**data).organization_id == 10


def test_client_cannot_supply_later_lifecycle_status():
    data = valid_donation_data()
    data["status"] = "collected"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


@pytest.mark.parametrize(
    "field_name",
    ["available_from", "pickup_deadline", "prepared_at"],
)
def test_timezone_is_required_for_all_timestamps(field_name):
    data = valid_donation_data()
    data[field_name] = "2026-11-15T09:00:00"

    with pytest.raises(ValidationError):
        DonationCreate(**data)


def test_timestamps_with_different_offsets_are_compared_as_instants():
    data = valid_donation_data()
    data["prepared_at"] = "2026-11-15T08:00:00+05:30"
    data["available_from"] = "2026-11-15T09:00:00+05:30"
    data["pickup_deadline"] = "2026-11-15T05:00:00+00:00"

    donation = DonationCreate(**data)

    assert donation.available_from.utcoffset() is not None
    assert donation.pickup_deadline.utcoffset() is not None


def test_deadline_before_available_from_in_utc_is_rejected():
    data = valid_donation_data()
    data["available_from"] = "2026-11-15T09:00:00+05:30"
    data["pickup_deadline"] = "2026-11-15T08:00:00+05:30"

    with pytest.raises(ValidationError):
        DonationCreate(**data)
