
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db.models.organization import (
    MemberStatus,
    MembershipRole,
    OrganizationMembership,
)
from scripts.seed_dev import ensure_membership


def make_test_data():
    org = SimpleNamespace(organization_id=10)
    user = SimpleNamespace(user_id=1)
    return org, user


def test_creates_membership_when_none_exists():
    session = MagicMock()
    session.scalar.return_value = None

    org, user = make_test_data()

    membership = ensure_membership(
        session,
        org,
        user,
        MembershipRole.owner,
    )

    assert isinstance(membership, OrganizationMembership)
    assert membership.organization_id == 10
    assert membership.user_id == 1
    assert membership.member_status == MemberStatus.active

    session.add.assert_called_once_with(membership)
    session.flush.assert_called_once()


def test_reuses_existing_active_membership():
    session = MagicMock()

    org, user = make_test_data()

    existing = SimpleNamespace(
        organization_id=10,
        user_id=1,
        member_status=MemberStatus.active,
    )

    session.scalar.return_value = existing

    result = ensure_membership(
        session,
        org,
        user,
        MembershipRole.owner,
    )

    assert result is existing
    session.add.assert_not_called()


def test_rejects_second_user_for_same_organization():
    session = MagicMock()

    org, user = make_test_data()

    existing = SimpleNamespace(
        organization_id=10,
        user_id=2,
        member_status=MemberStatus.active,
    )

    session.scalar.return_value = existing

    with pytest.raises(
        RuntimeError,
        match="already belongs to another user",
    ):
        ensure_membership(
            session,
            org,
            user,
            MembershipRole.owner,
        )

    session.add.assert_not_called()


def test_rejects_inactive_membership():
    session = MagicMock()

    org, user = make_test_data()

    existing = SimpleNamespace(
        organization_id=10,
        user_id=1,
        member_status=MemberStatus.removed,
    )

    session.scalar.return_value = existing

    with pytest.raises(
        RuntimeError,
        match="membership is not active",
    ):
        ensure_membership(
            session,
            org,
            user,
            MembershipRole.owner,
        )

    session.add.assert_not_called()
