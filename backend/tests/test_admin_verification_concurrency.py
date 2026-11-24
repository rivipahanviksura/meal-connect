from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.exception_handlers import APIException
from app.db.session import get_engine
from app.db.models.user import User, UserRole, AccountStatus
from app.db.models.organization import (
    Organization,
    OrganizationType,
    OrganizationMembership,
    OrganizationVerification,
    MembershipRole,
    MemberStatus,
    VerificationStatus,
)
from app.db.models.organization_document import (
    OrganizationApplicationSubmission,
    OrganizationDocument,
    OrganizationDocumentContent,
)
from app.db.models.status_history import StatusHistory
from app.services.admin_verification import (
    approve_application,
    reject_application,
    review_application_document,
)


def test_concurrent_admin_decisions():
    engine = get_engine()
    ids = None

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

        assert database_name == "meal_connect_test"

        unique_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc)

        with Session(engine) as db:
            admin_one = User(
                first_name="Concurrent",
                last_name="AdminOne",
                email=f"admin1-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.admin,
                account_status=AccountStatus.active,
            )

            admin_two = User(
                first_name="Concurrent",
                last_name="AdminTwo",
                email=f"admin2-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.admin,
                account_status=AccountStatus.active,
            )

            applicant = User(
                first_name="Concurrent",
                last_name="Applicant",
                email=f"applicant-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.business_staff,
                account_status=AccountStatus.active,
            )

            db.add_all([admin_one, admin_two, applicant])
            db.flush()

            organization = Organization(
                name="Concurrent Test Restaurant",
                type=OrganizationType.restaurant,
                registration_number=f"MEAL89-{unique_id}",
                contact_email=f"org-{unique_id}@example.com",
                address_line="Test Street",
                city="Colombo",
                representative_name="Test Applicant",
                submitted_at=now,
                verification_status=VerificationStatus.pending,
            )

            db.add(organization)
            db.flush()

            application_id = organization.organization_id

            db.add(
                OrganizationMembership(
                    organization_id=application_id,
                    user_id=applicant.user_id,
                    membership_role=MembershipRole.owner,
                    member_status=MemberStatus.active,
                )
            )

            db.add(
                OrganizationApplicationSubmission(
                    organization_id=application_id,
                    submitted_by_user_id=applicant.user_id,
                    submitted_at=now,
                    snapshot={
                        "organization_type": "restaurant",
                        "details": {},
                        "document_ids": {},
                    },
                )
            )

            ids = {
                "application_id": application_id,
                "admin_one": admin_one.user_id,
                "admin_two": admin_two.user_id,
                "applicant": applicant.user_id,
            }

            db.commit()

        barrier = Barrier(2)

        def attempt_rejection(admin_id):
            with Session(engine) as db:
                barrier.wait(timeout=15)

                try:
                    reject_application(
                        db=db,
                        application_id=ids["application_id"],
                        admin_id=admin_id,
                        reason="Registration evidence requires correction.",
                    )
                    return 200

                except APIException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                attempt_rejection,
                ids["admin_one"],
            )

            second = executor.submit(
                attempt_rejection,
                ids["admin_two"],
            )

            results = [
                first.result(timeout=30),
                second.result(timeout=30),
            ]

        assert sorted(results) == [200, 409]

        with Session(engine) as db:
            organization = db.get(
                Organization,
                ids["application_id"],
            )

            assert organization is not None
            assert (
                organization.verification_status
                == VerificationStatus.rejected
            )

            verification_count = db.scalar(
                select(func.count())
                .select_from(OrganizationVerification)
                .where(
                    OrganizationVerification.organization_id
                    == ids["application_id"]
                )
            )

            history_count = db.scalar(
                select(func.count())
                .select_from(StatusHistory)
                .where(
                    StatusHistory.entity_type == "organization",
                    StatusHistory.entity_id == ids["application_id"],
                    StatusHistory.new_status == "rejected",
                )
            )

            assert verification_count == 1
            assert history_count == 1

    finally:
        if ids is not None:
            with engine.begin() as connection:
                application_id = ids["application_id"]

                connection.execute(
                    delete(StatusHistory).where(
                        StatusHistory.entity_type == "organization",
                        StatusHistory.entity_id == application_id,
                    )
                )

                connection.execute(
                    delete(OrganizationVerification).where(
                        OrganizationVerification.organization_id
                        == application_id
                    )
                )

                connection.execute(
                    delete(OrganizationApplicationSubmission).where(
                        OrganizationApplicationSubmission.organization_id
                        == application_id
                    )
                )

                connection.execute(
                    delete(OrganizationMembership).where(
                        OrganizationMembership.organization_id
                        == application_id
                    )
                )

                connection.execute(
                    delete(Organization).where(
                        Organization.organization_id
                        == application_id
                    )
                )

                connection.execute(
                    delete(User).where(
                        User.user_id.in_([
                            ids["admin_one"],
                            ids["admin_two"],
                            ids["applicant"],
                        ])
                    )
                )

        engine.dispose()


def test_concurrent_approve_vs_reject():
    """Only one application decision may commit when two admins race."""
    engine = get_engine()
    ids = None

    try:
        # Do not write committed test records to any non-test database.
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
        assert database_name == "meal_connect_test"

        unique_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc)
        content = b"%PDF-1.4\nConcurrent registration evidence test"

        with Session(engine) as db:
            admin_one = User(
                first_name="Concurrent",
                last_name="ApproveAdmin",
                email=f"approve-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.admin,
                account_status=AccountStatus.active,
            )
            admin_two = User(
                first_name="Concurrent",
                last_name="RejectAdmin",
                email=f"reject-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.admin,
                account_status=AccountStatus.active,
            )
            applicant = User(
                first_name="Concurrent",
                last_name="Applicant",
                email=f"applicant-race-{unique_id}@example.com",
                password_hash="test-only",
                role=UserRole.business_staff,
                account_status=AccountStatus.active,
            )
            db.add_all([admin_one, admin_two, applicant])
            db.flush()

            organization = Organization(
                name="Concurrent Approval Restaurant",
                type=OrganizationType.restaurant,
                registration_number=f"MEAL89-RACE-{unique_id}",
                contact_email=f"org-race-{unique_id}@example.com",
                address_line="Test Street",
                city="Colombo",
                representative_name="Test Applicant",
                submitted_at=now,
                verification_status=VerificationStatus.pending,
            )
            db.add(organization)
            db.flush()
            application_id = organization.organization_id

            db.add(
                OrganizationMembership(
                    organization_id=application_id,
                    user_id=applicant.user_id,
                    membership_role=MembershipRole.owner,
                    member_status=MemberStatus.active,
                )
            )

            document = OrganizationDocument(
                organization_id=application_id,
                uploaded_by_user_id=applicant.user_id,
                document_type="registration_certificate",
                storage_key=uuid4().hex,
                original_filename="concurrent_registration.pdf",
                content_type="application/pdf",
                file_size_bytes=len(content),
                review_status="pending",
            )
            db.add(document)
            db.flush()

            db.add(
                OrganizationDocumentContent(
                    document_id=document.document_id,
                    content=content,
                )
            )

            db.add(
                OrganizationApplicationSubmission(
                    organization_id=application_id,
                    submitted_by_user_id=applicant.user_id,
                    submitted_at=now,
                    snapshot={
                        "organization_type": "restaurant",
                        "details": {},
                        "document_ids": {
                            "registration_certificate": document.document_id,
                        },
                    },
                )
            )

            ids = {
                "application_id": application_id,
                "document_id": document.document_id,
                "admin_one": admin_one.user_id,
                "admin_two": admin_two.user_id,
                "applicant": applicant.user_id,
            }
            db.commit()

        # Use the production service so the document has a genuine review audit.
        with Session(engine) as db:
            review_application_document(
                db=db,
                application_id=ids["application_id"],
                document_id=ids["document_id"],
                admin_id=ids["admin_one"],
                decision="approved",
                review_note="Registration evidence reviewed for concurrency test.",
            )

        barrier = Barrier(2)

        def attempt_decision(decision, admin_id):
            with Session(engine) as db:
                barrier.wait(timeout=15)
                try:
                    if decision == "approve":
                        approve_application(
                            db=db,
                            application_id=ids["application_id"],
                            admin_id=admin_id,
                            comment="Registration evidence reviewed and accepted.",
                        )
                    else:
                        reject_application(
                            db=db,
                            application_id=ids["application_id"],
                            admin_id=admin_id,
                            reason="Registration evidence requires correction.",
                        )
                    return 200
                except APIException as exc:
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                attempt_decision, "approve", ids["admin_one"]
            )
            second = executor.submit(
                attempt_decision, "reject", ids["admin_two"]
            )
            results = [first.result(timeout=30), second.result(timeout=30)]

        assert sorted(results) == [200, 409]

        with Session(engine) as db:
            organization = db.get(Organization, ids["application_id"])
            assert organization is not None
            assert organization.verification_status in {
                VerificationStatus.approved,
                VerificationStatus.rejected,
            }

            verification_records = db.scalars(
                select(OrganizationVerification).where(
                    OrganizationVerification.organization_id
                    == ids["application_id"]
                )
            ).all()
            assert len(verification_records) == 1
            assert verification_records[0].decision == organization.verification_status

            application_history = db.scalars(
                select(StatusHistory).where(
                    StatusHistory.entity_type == "organization",
                    StatusHistory.entity_id == ids["application_id"],
                )
            ).all()
            assert len(application_history) == 1
            assert application_history[0].new_status == (
                "verified"
                if organization.verification_status == VerificationStatus.approved
                else "rejected"
            )

            document_history_count = db.scalar(
                select(func.count()).select_from(StatusHistory).where(
                    StatusHistory.entity_type == "organization_document",
                    StatusHistory.entity_id == ids["document_id"],
                    StatusHistory.new_status == "approved",
                )
            )
            assert document_history_count == 1

    finally:
        if ids is not None:
            with engine.begin() as connection:
                application_id = ids["application_id"]
                document_id = ids["document_id"]

                # Delete only records created by this test, child tables first.
                connection.execute(
                    delete(StatusHistory).where(
                        StatusHistory.entity_type == "organization",
                        StatusHistory.entity_id == application_id,
                    )
                )
                connection.execute(
                    delete(StatusHistory).where(
                        StatusHistory.entity_type == "organization_document",
                        StatusHistory.entity_id == document_id,
                    )
                )
                connection.execute(
                    delete(OrganizationVerification).where(
                        OrganizationVerification.organization_id == application_id
                    )
                )
                connection.execute(
                    delete(OrganizationApplicationSubmission).where(
                        OrganizationApplicationSubmission.organization_id
                        == application_id
                    )
                )
                connection.execute(
                    delete(OrganizationDocumentContent).where(
                        OrganizationDocumentContent.document_id == document_id
                    )
                )
                connection.execute(
                    delete(OrganizationDocument).where(
                        OrganizationDocument.document_id == document_id
                    )
                )
                connection.execute(
                    delete(OrganizationMembership).where(
                        OrganizationMembership.organization_id == application_id
                    )
                )
                connection.execute(
                    delete(Organization).where(
                        Organization.organization_id == application_id
                    )
                )
                connection.execute(
                    delete(User).where(
                        User.user_id.in_([
                            ids["admin_one"],
                            ids["admin_two"],
                            ids["applicant"],
                        ])
                    )
                )

        engine.dispose()
