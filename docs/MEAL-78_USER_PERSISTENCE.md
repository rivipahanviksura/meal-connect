# MEAL-78 user persistence foundation

The feature branch synchronizes with develop and reuses `app.db.models.user.User`,
`app.db.base.Base` and `app.db.session`. No new users table or schema migration is
introduced. Use the existing Alembic workflow (`python -m alembic upgrade head`),
not `create_all()` or Alembic stamping to bypass missing migrations.

## Contract and ownership

`POST /api/v1/auth/register` uses `RegistrationRequest`, extending the shared
MEAL-74 `UserCreate` schema with required `account_type: business | ngo`.
The existing base schema remains compatible with other consumers.
The MEAL-80 refinement in `API_ENDPOINTS.md` supersedes the earlier placeholder
role wording in the decision record. Client role/status fields remain forbidden.
The backend assigns `business_staff` or `ngo_staff` and grants no organization
membership, verification or organization privileges.

The service accepts an already hashed password, normalizes emails, looks up
emails without case sensitivity, handles email conflicts and rolls back failed
writes. The existing unique email constraint protects concurrent normalized
registration writes. Legacy mixed-case emails are recognized by the lookup.
Responses expose only the existing safe UserResponse fields in a `data` wrapper;
409/503/500 errors use the canonical error envelope.

## MEAL-176 dependency (teammate owned)

No password hashing implementation or Argon2 dependency is added or modified by
MEAL-78. The integration seam loads `app.core.security.hash_password` if available.
Until the teammate's implementation and dependencies are integrated, the endpoint
returns 503 and writes no user. Do not declare registration complete yet.
No login, token generation or organization onboarding is implemented here.

## Validation

From `backend`: `python -m pytest -q`.
Persistence tests use a disposable SQLite database with a test-only BIGINT adapter;
production PostgreSQL model/migrations remain unchanged. A stub hasher exercises
the registration seam only and is never used by production code.
Coverage includes both account types, normalized lookup, duplicates including a
race at the unique constraint, rollback/recovery, non-email integrity failures,
forbidden privilege fields, safe responses and the pending-hashing 503 path.

Before final approval, run migrations on a disposable PostgreSQL database and
repeat registration/duplicate tests with the real MEAL-176 function. SQLite tests
do not establish PostgreSQL migration or complete authentication integration.
