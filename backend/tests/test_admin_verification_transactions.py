
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exception_handlers import APIException
from app.db.models.organization import (
    VerificationStatus,
    OrganizationVerification,
)
from app.db.models.status_history import StatusHistory
from app.services.admin_verification import reject_application


def make_organization():
    return SimpleNamespace(
        organization_id=10,
        verification_status=VerificationStatus.pending,
        verified_by_user_id=None,
        verified_at=None,
        updated_at=None,
    )


def test_rejection_updates_status_and_audit():
    db = MagicMock()
    organization = make_organization()
    submission = SimpleNamespace(submission_id=1)

    with patch(
        "app.services.admin_verification.lock_application",
        return_value=(organization, submission),
    ):
        result = reject_application(
            db=db,
            application_id=10,
            admin_id=5,
            reason="Registration evidence is incomplete",
        )

    assert organization.verification_status == VerificationStatus.rejected
    assert result.data.action == "reject"
    assert result.data.status == "rejected"
    assert result.data.reviewed_by_user_id == 5

    added_objects = [
        call.args[0] for call in db.add.call_args_list
    ]

    assert any(
        isinstance(item, OrganizationVerification)
        for item in added_objects
    )

    assert any(
        isinstance(item, StatusHistory)
        for item in added_objects
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_duplicate_rejection_rolls_back():
    db = MagicMock()

    with patch(
        "app.services.admin_verification.lock_application",
        side_effect=APIException(
            status_code=409,
            code="INVALID_STATE_TRANSITION",
            message="Application is not awaiting review.",
        ),
    ):
        with pytest.raises(APIException) as exc:
            reject_application(
                db=db,
                application_id=10,
                admin_id=5,
                reason="Registration evidence is incomplete",
            )

    assert exc.value.status_code == 409
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_database_failure_rolls_back():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("Simulated database error")

    organization = make_organization()
    submission = SimpleNamespace(submission_id=1)

    with patch(
        "app.services.admin_verification.lock_application",
        return_value=(organization, submission),
    ):
        with pytest.raises(RuntimeError):
            reject_application(
                db=db,
                application_id=10,
                admin_id=5,
                reason="Registration evidence is incomplete",
            )

    db.rollback.assert_called_once()


def test_short_rejection_reason_is_rejected():
    db = MagicMock()

    with pytest.raises(APIException) as exc:
        reject_application(
            db=db,
            application_id=10,
            admin_id=5,
            reason="Missing",
        )

    assert exc.value.status_code == 422
    db.commit.assert_not_called()


from app.services.admin_verification import approve_application


def test_approval_updates_status_and_audit():
    db = MagicMock()
    organization = make_organization()
    submission = SimpleNamespace(submission_id=1)

    with (
        patch(
            "app.services.admin_verification.lock_application",
            return_value=(organization, submission),
        ),
        patch(
            "app.services.admin_verification.validate_organization_details"
        ),
        patch(
            "app.services.admin_verification.check_registration_evidence"
        ),
        patch(
            "app.services.admin_verification.validate_approval_membership"
        ),
    ):
        result = approve_application(
            db=db,
            application_id=10,
            admin_id=5,
            comment="Registration evidence reviewed and accepted.",
        )

    assert organization.verification_status == VerificationStatus.approved
    assert organization.verified_by_user_id == 5
    assert organization.verified_at is not None

    assert result.data.action == "approve"
    assert result.data.status == "verified"

    added_objects = [
        call.args[0]
        for call in db.add.call_args_list
    ]

    assert any(
        isinstance(item, OrganizationVerification)
        for item in added_objects
    )

    assert any(
        isinstance(item, StatusHistory)
        for item in added_objects
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_approval_validation_failure_rolls_back():
    db = MagicMock()
    organization = make_organization()
    submission = SimpleNamespace(submission_id=1)

    with (
        patch(
            "app.services.admin_verification.lock_application",
            return_value=(organization, submission),
        ),
        patch(
            "app.services.admin_verification.validate_organization_details",
            side_effect=APIException(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Required organization information is missing.",
            ),
        ),
    ):
        with pytest.raises(APIException) as exc:
            approve_application(
                db=db,
                application_id=10,
                admin_id=5,
                comment="Registration evidence reviewed and accepted.",
            )

    assert exc.value.status_code == 422
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_approval_database_failure_rolls_back():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("Simulated database error")

    organization = make_organization()
    submission = SimpleNamespace(submission_id=1)

    with (
        patch(
            "app.services.admin_verification.lock_application",
            return_value=(organization, submission),
        ),
        patch(
            "app.services.admin_verification.validate_organization_details"
        ),
        patch(
            "app.services.admin_verification.check_registration_evidence"
        ),
        patch(
            "app.services.admin_verification.validate_approval_membership"
        ),
    ):
        with pytest.raises(RuntimeError):
            approve_application(
                db=db,
                application_id=10,
                admin_id=5,
                comment="Registration evidence reviewed and accepted.",
            )

    db.rollback.assert_called_once()


def test_approval_rejects_short_comment():
    db = MagicMock()

    with pytest.raises(APIException) as exc:
        approve_application(
            db=db,
            application_id=10,
            admin_id=5,
            comment="OK",
        )

    assert exc.value.status_code == 422
    db.commit.assert_not_called()


from app.db.models.organization import (
    OrganizationType,
    MembershipRole,
    MemberStatus,
)

from app.db.models.user import UserRole, AccountStatus

from app.services.admin_verification import validate_approval_membership


def make_approval_context(role=UserRole.business_staff):
    db = MagicMock()

    organization = SimpleNamespace(
        organization_id=10,
        type=OrganizationType.restaurant,
    )

    submission = SimpleNamespace(
        submitted_by_user_id=7,
    )

    membership = SimpleNamespace(
        user_id=7,
        membership_role=MembershipRole.owner,
        member_status=MemberStatus.active,
    )

    owner = SimpleNamespace(
        user_id=7,
        role=role,
        account_status=AccountStatus.active,
    )

    db.scalar.side_effect = [membership, None]
    db.get.return_value = owner

    return db, organization, submission


def test_valid_business_membership():
    db, organization, submission = make_approval_context()

    validate_approval_membership(
        db,
        organization,
        submission,
    )


def test_wrong_role_blocks_approval():
    db, organization, submission = make_approval_context(
        role=UserRole.ngo_staff
    )

    with pytest.raises(APIException) as exc:
        validate_approval_membership(
            db,
            organization,
            submission,
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "ROLE_MISMATCH"


def test_inactive_owner_blocks_approval():
    db, organization, submission = make_approval_context()

    db.get.return_value.account_status = AccountStatus.suspended

    with pytest.raises(APIException) as exc:
        validate_approval_membership(
            db,
            organization,
            submission,
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "INACTIVE_APPLICANT"


def test_missing_owner_blocks_approval():
    db, organization, submission = make_approval_context()

    db.scalar.side_effect = [None]

    with pytest.raises(APIException) as exc:
        validate_approval_membership(
            db,
            organization,
            submission,
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "INVALID_MEMBERSHIP"


def test_multiple_organizations_block_approval():
    db, organization, submission = make_approval_context()

    db.scalar.side_effect = [SimpleNamespace(user_id=7), 99]

    with pytest.raises(APIException) as exc:
        validate_approval_membership(
            db,
            organization,
            submission,
        )

    assert exc.value.status_code == 409
    assert exc.value.code == "MULTIPLE_ORGANIZATIONS"
