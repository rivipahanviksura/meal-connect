from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    Organization,
    OrganizationMembership,
    OrganizationType,
    VerificationStatus,
)
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_db, get_engine
from app.main import app


TEST_KEY = "meal215-applicant-test-signing-key-0123456789"
TEST_PASSWORD = "ApplicantTestPassword123!"


@pytest.fixture
def db():
    assert settings.database_url is not None

    url = make_url(settings.database_url.get_secret_value())

    assert url.get_backend_name() == "postgresql"
    assert url.database == "meal_connect_test"
    assert url.host in {"localhost", "127.0.0.1", "::1"}

    engine = get_engine()

    try:
        with engine.connect() as connection:
            actual_database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            assert actual_database == "meal_connect_test"

            connection.rollback()
            transaction = connection.begin()

            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
            )

            try:
                yield session
            finally:
                session.close()
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(
        settings,
        "secret_key",
        SecretStr(TEST_KEY),
    )
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(
        settings,
        "access_token_expire_minutes",
        15,
    )

    previous_overrides = app.dependency_overrides.copy()

    def override_db():
        yield db

    # Only the database dependency is replaced.
    # Login, password verification and JWT authentication remain real.
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def create_applicant(db, account_type, verification_status, member_status):
    unique_id = uuid4().hex

    role = (
        UserRole.business_staff
        if account_type == "business"
        else UserRole.ngo_staff
    )

    organization_type = (
        OrganizationType.restaurant
        if account_type == "business"
        else OrganizationType.ngo
    )

    user = User(
        first_name="QA",
        last_name="Applicant",
        email=f"meal215_{unique_id}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        account_status=AccountStatus.active,
    )
    db.add(user)
    db.flush()

    organization = Organization(
        name=f"Private Application {unique_id}",
        type=organization_type,
        registration_number=f"QA-{unique_id}",
        registration_authority="QA Test Authority",
        contact_email=f"org_{unique_id}@example.com",
        address_line="QA test address",
        city="Kurunegala",
        representative_name="QA Applicant",
        verification_status=verification_status,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(organization)
    db.flush()

    user_id = user.user_id
    organization_id = organization.organization_id
    email = user.email

    db.add(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user_id,
            membership_role=MembershipRole.owner,
            member_status=member_status,
        )
    )
    db.commit()

    return email, user_id, organization_id


def assert_no_secrets(response, stored_hash, token=None):
    assert TEST_PASSWORD not in response.text
    assert stored_hash not in response.text
    assert TEST_KEY not in response.text
    assert "password_hash" not in response.text

    if token is not None:
        assert token not in response.text


@pytest.mark.parametrize("account_type", ["business", "ngo"])
@pytest.mark.parametrize(
    "verification_status",
    [
        VerificationStatus.pending,
        VerificationStatus.rejected,
    ],
)
@pytest.mark.parametrize(
    "member_status",
    [
        MemberStatus.invited,
        MemberStatus.active,
    ],
)
def test_applicant_can_login_and_view_status_but_not_use_protected_api(
    db,
    client,
    account_type,
    verification_status,
    member_status,
):
    email, user_id, organization_id = create_applicant(
        db,
        account_type,
        verification_status,
        member_status,
    )

    stored_hash = db.get(User, user_id).password_hash

    # 1. Real login must work for active pending/rejected applicants.
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login.status_code == 200, login.text

    login_data = login.json()["data"]
    token = login_data["access_token"]

    assert token
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["user_id"] == user_id
    assert_no_secrets(login, stored_hash)

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Applicants must be able to view their own application.
    own_status = client.get(
        "/api/v1/organization-applications/me",
        headers=headers,
    )

    assert own_status.status_code == 200, own_status.text

    applications = own_status.json()["data"]

    assert len(applications) == 1
    assert applications[0]["organization_id"] == organization_id
    assert applications[0]["application_id"] == organization_id

    expected_status = (
        "pending_verification"
        if verification_status == VerificationStatus.pending
        else "rejected"
    )

    assert applications[0]["status"] == expected_status
    assert_no_secrets(own_status, stored_hash, token)

    # 3. Organization privileges must remain blocked.
    if account_type == "ngo":
        protected = client.get(
            "/api/v1/donations",
            headers=headers,
        )
    else:
        protected = client.patch(
            "/api/v1/donations/1",
            headers=headers,
            json={"title": "Unauthorized update"},
        )

    assert protected.status_code == 403, protected.text

    error = protected.json()["error"]

    assert error["code"] == "FORBIDDEN"
    assert isinstance(error["message"], str)
    assert error["message"]
    assert error["fields"] == []

    assert_no_secrets(protected, stored_hash, token)