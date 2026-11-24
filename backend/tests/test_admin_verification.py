
from types import SimpleNamespace

import pytest

from app.core.exception_handlers import APIException
from app.db.models.organization import OrganizationType
from app.services.admin_verification import (
    validate_organization_details,
)


def make_organization(**changes):
    data = {
        "name": "Test Restaurant",
        "registration_number": "BR-12345",
        "contact_email": "test@example.com",
        "address_line": "Colombo",
        "city": "Colombo",
        "representative_name": "Test Owner",
        "type": OrganizationType.restaurant,
        "registration_authority": None,
        "operational_details": None,
    }

    data.update(changes)
    return SimpleNamespace(**data)


def test_valid_restaurant_details():
    organization = make_organization()

    validate_organization_details(organization)


def test_missing_registration_number():
    organization = make_organization(
        registration_number=None
    )

    with pytest.raises(APIException) as exc:
        validate_organization_details(organization)

    assert exc.value.status_code == 422
    assert exc.value.code == "VALIDATION_ERROR"


def test_missing_representative():
    organization = make_organization(
        representative_name=""
    )

    with pytest.raises(APIException) as exc:
        validate_organization_details(organization)

    assert exc.value.status_code == 422


def test_valid_ngo_details():
    organization = make_organization(
        type=OrganizationType.ngo,
        registration_authority="NGO Secretariat",
        operational_details={
            "operational_capability": "Food distribution"
        },
    )

    validate_organization_details(organization)


def test_missing_ngo_operational_capability():
    organization = make_organization(
        type=OrganizationType.ngo,
        registration_authority="NGO Secretariat",
        operational_details={},
    )

    with pytest.raises(APIException) as exc:
        validate_organization_details(organization)

    assert exc.value.status_code == 422

from pydantic import ValidationError

from app.schemas.admin_verification import (
    AdminApproveRequest,
    AdminCorrectionRequest,
    AdminRejectRequest,
)


def test_valid_correction_reason():
    request = AdminCorrectionRequest(
        reason="Please upload the missing registration evidence."
    )

    assert request.reason == (
        "Please upload the missing registration evidence."
    )


def test_empty_correction_reason_rejected():
    with pytest.raises(ValidationError):
        AdminCorrectionRequest(reason="")


def test_short_correction_reason_rejected():
    with pytest.raises(ValidationError):
        AdminCorrectionRequest(reason="Missing")


def test_correction_rejects_admin_identity():
    with pytest.raises(ValidationError):
        AdminCorrectionRequest(
            reason="Please provide the required supporting documents.",
            reviewed_by_user_id=123,
        )


def test_correction_rejects_status_override():
    with pytest.raises(ValidationError):
        AdminCorrectionRequest(
            reason="Please update the organization details.",
            verification_status="approved",
        )


def test_approval_does_not_accept_role_override():
    with pytest.raises(ValidationError):
        AdminApproveRequest(
            comment="Documents reviewed.",
            role="admin",
        )
