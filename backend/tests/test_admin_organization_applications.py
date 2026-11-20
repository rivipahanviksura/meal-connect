from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.db.models.user import User, UserRole, AccountStatus
from app.db.models.organization import (
    Organization,
    OrganizationType,
    VerificationStatus,
    OrganizationVerification,
)
from app.db.models.organization_document import (
    OrganizationDocument,
    OrganizationDocumentContent,
    OrganizationApplicationSubmission,
)
from app.db.models.status_history import StatusHistory


NOW = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(element, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    User.__table__.create(engine)
    Organization.__table__.create(engine)
    OrganizationDocument.__table__.create(engine)
    OrganizationDocumentContent.__table__.create(engine)
    OrganizationApplicationSubmission.__table__.create(engine)
    OrganizationVerification.__table__.create(engine)
    StatusHistory.__table__.create(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr("meal88-test-only-nonproduction-secret"),
    )
    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: db)

    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)


def create_user(
    db,
    user_id,
    role=UserRole.admin,
    account_status=AccountStatus.active,
):
    user = User(
        user_id=user_id,
        first_name=f"Test{user_id}",
        last_name="User",
        email=f"user{user_id}@example.com",
        password_hash="test-only-placeholder",
        role=role,
        account_status=account_status,
    )
    db.add(user)
    db.flush()
    return user


def create_application(
    db,
    application_id,
    *,
    organization_type=OrganizationType.restaurant,
    verification_status=VerificationStatus.pending,
    submitted_at=NOW,
):
    organization = Organization(
        organization_id=application_id,
        name=f"Organization {application_id}",
        type=organization_type,
        registration_number=f"REG-{application_id}",
        contact_email=f"org{application_id}@example.com",
        contact_phone="0711234567",
        address_line="Test address",
        city="Colombo",
        district="Colombo",
        registration_authority="Test authority",
        representative_name="Test Representative",
        representative_designation="Director",
        pickup_location="Test premises",
        operational_details={"capacity": 100},
        submitted_at=submitted_at,
        verification_status=verification_status,
    )
    db.add(organization)
    db.flush()
    return organization


def admin_headers(user_id=1):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_queue_requires_authentication(client):
    response = client.get("/api/v1/admin/organization-applications")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize(
    "role,account_status",
    [
        (UserRole.business_staff, AccountStatus.active),
        (UserRole.ngo_staff, AccountStatus.active),
        (UserRole.volunteer, AccountStatus.active),
        (UserRole.admin, AccountStatus.suspended),
        (UserRole.admin, AccountStatus.disabled),
    ],
)
def test_non_active_admin_cannot_access_queue(
    db,
    client,
    role,
    account_status,
):
    create_user(
        db,
        1,
        role=role,
        account_status=account_status,
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications",
        headers=admin_headers(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_admin_queue_returns_only_submitted_pending_applications(db, client):
    create_user(db, 1)

    create_application(db, 1, submitted_at=NOW)
    create_application(
        db,
        2,
        submitted_at=None,
    )
    create_application(
        db,
        3,
        verification_status=VerificationStatus.approved,
    )
    create_application(
        db,
        4,
        verification_status=VerificationStatus.rejected,
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications",
        headers=admin_headers(),
    )

    assert response.status_code == 200
    result = response.json()

    assert [item["application_id"] for item in result["data"]] == [1]
    assert result["data"][0]["organization_name"] == "Organization 1"
    assert result["data"][0]["verification_status"] == "pending"
    assert result["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total_items": 1,
        "total_pages": 1,
    }


def test_queue_filters_by_organization_type_and_status(db, client):
    create_user(db, 1)

    create_application(db, 1, organization_type=OrganizationType.restaurant)
    create_application(db, 2, organization_type=OrganizationType.ngo)
    create_application(
        db,
        3,
        organization_type=OrganizationType.ngo,
        verification_status=VerificationStatus.rejected,
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications",
        headers=admin_headers(),
        params={
            "organization_type": "ngo",
            "status": "pending",
        },
    )

    assert response.status_code == 200
    assert [item["application_id"] for item in response.json()["data"]] == [2]


def test_queue_paginates_and_sorts_newest_first(db, client):
    create_user(db, 1)

    create_application(
        db,
        1,
        submitted_at=datetime(2026, 11, 18, tzinfo=timezone.utc),
    )
    create_application(
        db,
        2,
        submitted_at=datetime(2026, 11, 19, tzinfo=timezone.utc),
    )
    create_application(
        db,
        3,
        submitted_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications",
        headers=admin_headers(),
        params={"page": 1, "page_size": 2},
    )

    assert response.status_code == 200
    result = response.json()

    assert [item["application_id"] for item in result["data"]] == [3, 2]
    assert result["pagination"]["total_items"] == 3
    assert result["pagination"]["total_pages"] == 2


def test_invalid_queue_filters_return_validation_error(db, client):
    create_user(db, 1)
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications",
        headers=admin_headers(),
        params={"organization_type": "invalid"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["fields"]


def test_admin_can_view_application_details_and_history(db, client):
    create_user(db, 1)
    create_user(db, 2)

    create_application(db, 10)

    db.add(
        OrganizationDocument(
            document_id=100,
            organization_id=10,
            uploaded_by_user_id=2,
            document_type="registration_certificate",
            storage_key="private-secret-storage-key",
            original_filename="registration.pdf",
            content_type="application/pdf",
            file_size_bytes=120,
            review_status="pending",
            uploaded_at=NOW,
        )
    )

    db.add(
        OrganizationDocumentContent(
            document_id=100,
            content=b"test-pdf-content",
        )
    )

    db.add(
        OrganizationApplicationSubmission(
            submission_id=200,
            organization_id=10,
            submitted_by_user_id=2,
            submitted_at=NOW,
            snapshot={
                "organization_type": "restaurant",
                "document_ids": [100],
            },
        )
    )

    db.add(
        OrganizationVerification(
            verification_id=300,
            organization_id=10,
            reviewed_by_user_id=2,
            decision=VerificationStatus.rejected,
            review_note="Please provide a clearer certificate.",
            reviewed_at=NOW,
        )
    )

    db.add(
        StatusHistory(
            status_history_id=400,
            entity_type="organization",
            entity_id=10,
            old_status="draft",
            new_status="pending_verification",
            changed_by_user_id=2,
            change_reason="Application submitted",
            changed_at=NOW,
        )
    )

    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications/10",
        headers=admin_headers(),
    )

    assert response.status_code == 200
    result = response.json()["data"]

    assert result["application_id"] == 10
    assert result["name"] == "Organization 10"
    assert result["organization_type"] == "restaurant"
    assert result["representative_name"] == "Test Representative"

    assert len(result["documents"]) == 1
    assert result["documents"][0]["document_type"] == "registration_certificate"
    assert "storage_key" not in result["documents"][0]

    assert len(result["submissions"]) == 1
    assert len(result["reviews"]) == 1
    assert result["reviews"][0]["review_note"] == (
        "Please provide a clearer certificate."
    )
    assert result["reviews"][0]["reviewer_name"] == "Test2 User"

    assert len(result["status_history"]) == 1
    assert result["status_history"][0]["new_status"] == "pending_verification"


def test_admin_cannot_view_draft_application(db, client):
    create_user(db, 1)
    create_application(db, 10, submitted_at=None)
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications/10",
        headers=admin_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_admin_can_download_application_document_securely(db, client):
    create_user(db, 1)
    create_user(db, 2)
    create_application(db, 10)

    db.add(
        OrganizationDocument(
            document_id=100,
            organization_id=10,
            uploaded_by_user_id=2,
            document_type="registration_certificate",
            storage_key="private-secret-storage-key",
            original_filename="registration.pdf",
            content_type="application/pdf",
            file_size_bytes=120,
            review_status="pending",
            uploaded_at=NOW,
        )
    )
    db.add(
        OrganizationDocumentContent(
            document_id=100,
            content=b"test-pdf-content",
        )
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications/10/documents/100",
        headers=admin_headers(),
    )

    assert response.status_code == 200
    assert response.content == b"test-pdf-content"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"
    assert "attachment" in response.headers["content-disposition"]
    assert "private-secret-storage-key" not in response.text


def test_admin_cannot_download_document_from_another_application(db, client):
    create_user(db, 1)
    create_user(db, 2)
    create_application(db, 10)
    create_application(db, 20)

    db.add(
        OrganizationDocument(
            document_id=100,
            organization_id=20,
            uploaded_by_user_id=2,
            document_type="registration_certificate",
            storage_key="another-private-storage-key",
            original_filename="other.pdf",
            content_type="application/pdf",
            file_size_bytes=120,
            review_status="pending",
            uploaded_at=NOW,
        )
    )
    db.add(
        OrganizationDocumentContent(
            document_id=100,
            content=b"other-document-content",
        )
    )
    db.commit()

    response = client.get(
        "/api/v1/admin/organization-applications/10/documents/100",
        headers=admin_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
