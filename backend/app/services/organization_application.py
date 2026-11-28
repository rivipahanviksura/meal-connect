
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.organization import (
    MembershipRole,
    MemberStatus,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.schemas.organization_application import (
    ApplicationDetails,
    ApplicationDraft,
    ApplicationRequest,
    BusinessApplication,
    NgoOperationalDetails,
)


class ApplicantNotAllowedError(Exception):
    pass


class ApplicationAlreadyExistsError(Exception):
    pass


class RegistrationNumberAlreadyExistsError(Exception):
    pass


def require_applicant(user: User | None) -> User:
    if (
        user is None
        or user.account_status != AccountStatus.active
        or user.role not in (
            UserRole.business_staff,
            UserRole.ngo_staff,
        )
    ):
        raise ApplicantNotAllowedError

    return user


def create_application_draft(
    db: Session,
    authenticated_user_id: int,
    request: ApplicationRequest,
) -> ApplicationDraft:
    """Create the organization and owning membership in one transaction."""

    try:
        # Lock the applicant row to serialize concurrent draft creation.
        applicant = require_applicant(
            db.scalar(
                select(User)
                .where(User.user_id == authenticated_user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

        if isinstance(request, BusinessApplication):
            expected_role = UserRole.business_staff
            organization_type = OrganizationType(
                request.business_subtype
            )
        else:
            expected_role = UserRole.ngo_staff
            organization_type = OrganizationType.ngo

        if applicant.role != expected_role:
            raise ApplicantNotAllowedError

        membership_exists = db.scalar(
            select(OrganizationMembership.membership_id)
            .where(
                OrganizationMembership.user_id == applicant.user_id
            )
            .limit(1)
        )

        if membership_exists is not None:
            raise ApplicationAlreadyExistsError

        organization = Organization(
            **request.model_dump(
                exclude={
                    "organization_type",
                    "business_subtype",
                }
            ),
            type=organization_type,
            verification_status=VerificationStatus.pending,
        )

        db.add(organization)
        db.flush()

        organization_id = organization.organization_id

        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=applicant.user_id,
            membership_role=MembershipRole.owner,
            member_status=MemberStatus.invited,
        )

        db.add(membership)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        constraint_name = getattr(
            getattr(exc.orig, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name in {
            "organizations_registration_number_key",
            "uq_organizations_registration_identity",
        }:
            raise RegistrationNumberAlreadyExistsError from exc

        if constraint_name == "uq_membership_single_org_per_user":
            raise ApplicationAlreadyExistsError from exc

        raise

    except Exception:
        db.rollback()
        raise

    return ApplicationDraft(
        application_id=organization_id,
        organization_id=organization_id,
    )


def get_application_details(
    organization: Organization,
) -> dict:
    details = {
        field: getattr(organization, field)
        for field in ApplicationDetails.model_fields
    }

    if organization.type == OrganizationType.ngo:
        operations = organization.operational_details

        details.update(
            registration_authority=organization.registration_authority,
            registration_date=(
                organization.registration_date.isoformat()
                if organization.registration_date
                else None
            ),
            operational_details={
                field: operations.get(field)
                for field in NgoOperationalDetails.model_fields
            }
            if isinstance(operations, dict)
            else None,
        )

    else:
        details["pickup_location"] = organization.pickup_location

    return details


def get_own_application(
    db: Session,
    authenticated_user_id: int,
) -> Organization | None:
    applicant = require_applicant(
        db.get(
            User,
            authenticated_user_id,
            populate_existing=True,
        )
    )

    return db.scalar(
        select(Organization)
        .join(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == applicant.user_id,
            OrganizationMembership.membership_role == MembershipRole.owner,
            OrganizationMembership.member_status.in_(
                (
                    MemberStatus.invited,
                    MemberStatus.active,
                )
            ),
        )
    )
