# MEAL-85 PostgreSQL Migration Integration Tests

## Purpose

These opt-in tests verify the MEAL-85 migration against real PostgreSQL databases.
They cover NULLS NOT DISTINCT behavior, membership uniqueness, and migration preflight checks.

Use only disposable databases whose names start with `meal85_`.
The tests never create or drop databases.

## PostgreSQL version

PostgreSQL 15 or later is required because the migration uses `NULLS NOT DISTINCT`.
The project local setup specifies PostgreSQL 17.

Check the server version:

```bash
psql -d postgres -c "SHOW server_version;"
```

## Required disposable databases

Prepare two disposable PostgreSQL databases before running the tests:

- `meal85_migration_test`: upgraded to revision `57cacefc56a2`; it must contain two organizations with the same non-null registration number but different organization types.
- `meal85_upgrade_test`: upgraded to parent revision `e721c958e76a`; it must contain one user with memberships in two organizations.

The integration tests verify these prerequisites and do not create or drop databases.

## Run the integration tests

Run from the `backend` directory:

```bash
MEAL85_TEST_DATABASE_URL='postgresql+psycopg://admin@localhost/meal85_migration_test' \
MEAL85_UPGRADE_TEST_DATABASE_URL='postgresql+psycopg://admin@localhost/meal85_upgrade_test' \
python -m pytest tests/test_meal85_postgres_integration.py -v
```

Both environment variables are required. Without them, the opt-in tests are skipped.

Expected result: 3 passed.

## Safety

- Use only disposable databases with names beginning with `meal85_`.
- Never use development, production, or shared team databases.
- The constraint test rolls back its inserted records.
- The migration preflight tests intentionally retain their prepared conflict records.
