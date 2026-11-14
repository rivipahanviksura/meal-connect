from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles

from app.api.auth import get_password_hasher
from app.db.models.user import AccountStatus, User, UserRole
from app.db.session import get_db
from app.main import app
from app.schemas.user import RegistrationRequest
from app.services.user_service import DuplicateEmailError, create_user_record, get_user_by_email


# SQLite test adapter only: production keeps PostgreSQL BIGINT/Identity unchanged.
@compiles(BigInteger, 'sqlite')
def sqlite_bigint(element, compiler, **kw):
    return 'INTEGER'


@pytest.fixture
def db():
    engine = create_engine('sqlite://', poolclass=StaticPool,
                           connect_args={'check_same_thread': False})
    User.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def payload():
    return dict(first_name='Demo', last_name='User', email='DEMO@example.com',
                password='ExamplePassword123!', account_type='ngo')


@pytest.fixture
def client(db):
    def override_db():
        yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_password_hasher] = lambda: None
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(('account_type', 'role'), [('ngo', UserRole.ngo_staff),
                                                   ('business', UserRole.business_staff)])
def test_create_and_lookup(db, payload, account_type, role):
    payload['account_type'] = account_type
    user = create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    assert user.user_id is not None
    assert user.role == role
    assert user.account_status == AccountStatus.active
    assert user.email == 'demo@example.com'
    assert user.first_name == 'Demo' and user.last_name == 'User'
    assert user.created_at and user.updated_at
    assert get_user_by_email(db, '  DEMO@EXAMPLE.COM  ').user_id == user.user_id
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_duplicate_and_session_recovery(db, payload):
    request = RegistrationRequest(**payload)
    create_user_record(db, request, 'test-hash')
    with pytest.raises(DuplicateEmailError):
        create_user_record(db, request, 'test-hash')
    payload['email'] = 'other@example.com'
    assert create_user_record(db, RegistrationRequest(**payload), 'test-hash').user_id


def test_flush_failure_rolls_back(db, payload, monkeypatch):
    original_flush = db.flush
    monkeypatch.setattr(db, 'flush', Mock(side_effect=SQLAlchemyError('private SQL')))
    with pytest.raises(SQLAlchemyError):
        create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    monkeypatch.setattr(db, 'flush', original_flush)
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert create_user_record(db, RegistrationRequest(**payload), 'test-hash').user_id


def test_racing_duplicate_rolls_back(db, payload, monkeypatch):
    create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    monkeypatch.setattr('app.services.user_service.get_user_by_email', lambda *args: None)
    with pytest.raises(DuplicateEmailError):
        create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_other_integrity_error_is_not_email_conflict(db, payload, monkeypatch):
    monkeypatch.setattr(db, 'flush', Mock(side_effect=IntegrityError('SQL', {}, Exception('other constraint'))))
    with pytest.raises(IntegrityError):
        create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    assert not db.new


@pytest.mark.parametrize('password_hash', ['', 'ExamplePassword123!'])
def test_reject_raw_or_empty_password(db, payload, password_hash):
    with pytest.raises(ValueError):
        create_user_record(db, RegistrationRequest(**payload), password_hash)
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_hashing_pending_creates_nothing(client, db, payload):
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 503
    assert response.json()['error']['fields'] == []
    assert db.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.parametrize('extra', [{'role': 'admin'}, {'account_status': 'active'},
                                  {'account_type': 'volunteer'}, {'account_type': 'admin'}])
def test_public_privilege_fields_rejected(client, payload, extra):
    payload.update(extra)
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 422
    assert payload['password'] not in response.text


def test_registration_contract_with_stub_hasher(client, db, payload):
    # Tests the MEAL-78 integration seam, not MEAL-176 cryptography.
    app.dependency_overrides[get_password_hasher] = lambda: lambda password: 'test-hash'
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 201
    assert response.json()['data']['role'] == 'ngo_staff'
    assert 'password' not in response.text and 'test-hash' not in response.text
    assert get_user_by_email(db, payload['email']).password_hash == 'test-hash'
    duplicate = client.post('/api/v1/auth/register', json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json() == {'error': {'code': 'ALREADY_EXISTS',
                                          'message': 'Email already registered', 'fields': []}}


def test_database_error_is_safe(client, payload, monkeypatch):
    app.dependency_overrides[get_password_hasher] = lambda: lambda password: 'test-hash'
    monkeypatch.setattr('app.api.auth.create_user_record', Mock(side_effect=SQLAlchemyError('secret SQL')))
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 500
    assert 'secret' not in response.text
    assert response.json()['error']['fields'] == []


def test_required_account_type(client, payload):
    del payload['account_type']
    response = client.post('/api/v1/auth/register', json=payload)
    assert response.status_code == 422
    assert any(field['field'] == 'account_type'
               for field in response.json()['error']['fields'])


def test_postgres_email_constraint_rolls_back(db, payload, monkeypatch):
    original_flush = db.flush
    class PostgresUniqueError(Exception):
        diag = type('Diagnostic', (), {'constraint_name': 'users_email_key'})()
    monkeypatch.setattr(db, 'flush', Mock(side_effect=IntegrityError('SQL', {}, PostgresUniqueError())))
    with pytest.raises(DuplicateEmailError):
        create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    monkeypatch.setattr(db, 'flush', original_flush)
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_commit_failure_rolls_back(db, payload, monkeypatch):
    original_commit = db.commit
    monkeypatch.setattr(db, 'commit', Mock(side_effect=SQLAlchemyError('private commit error')))
    with pytest.raises(SQLAlchemyError):
        create_user_record(db, RegistrationRequest(**payload), 'test-hash')
    monkeypatch.setattr(db, 'commit', original_commit)
    assert db.scalar(select(func.count()).select_from(User)) == 0
    assert create_user_record(db, RegistrationRequest(**payload), 'test-hash').user_id
