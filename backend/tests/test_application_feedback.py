
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.organization_application import application_summary
from app.db.models.organization import VerificationStatus


def create_organization(status):
    return SimpleNamespace(
        organization_id=10,
        name="Test Restaurant",
        verification_status=status,
        submitted_at="2026-11-23",
    )


@pytest.mark.parametrize(
    "status,expected_status",
    [
        (VerificationStatus.pending, "pending_verification"),
        (VerificationStatus.approved, "verified"),
        (VerificationStatus.suspended, "suspended"),
    ],
)
def test_application_status_is_displayed(
    status,
    expected_status,
):
    db = MagicMock()
    organization = create_organization(status)

    result = application_summary(db, organization)

    assert result.application_id == 10
    assert result.organization_id == 10
    assert result.status == expected_status
    assert result.review_note is None

    db.scalar.assert_not_called()


def test_rejected_application_displays_reason():
    db = MagicMock()
    db.scalar.return_value = (
        "Registration certificate is incomplete."
    )

    organization = create_organization(
        VerificationStatus.rejected
    )

    result = application_summary(db, organization)

    assert result.status == "rejected"
    assert result.review_note == (
        "Registration certificate is incomplete."
    )
    db.scalar.assert_called_once()


def test_corrections_request_displays_feedback():
    db = MagicMock()
    db.scalar.return_value = (
        "Corrections requested: Upload a clearer certificate."
    )

    organization = create_organization(
        VerificationStatus.rejected
    )

    result = application_summary(db, organization)

    assert result.status == "rejected"
    assert result.review_note.startswith(
        "Corrections requested:"
    )
    db.scalar.assert_called_once()
