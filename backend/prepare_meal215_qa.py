"""Run manually from the backend folder, using its existing virtual environment."""
import argparse
import json
import secrets
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import get_engine
from app.db.models.user import AccountStatus, User, UserRole


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Output exists. Reuse the existing qa-admin.json or choose a new filename.')
    if settings.database_url is None:
        raise SystemExit('DATABASE_URL must be configured.')
    url = make_url(settings.database_url.get_secret_value())
    if url.database != 'meal_connect_test' or url.host not in {'localhost', '127.0.0.1'}:
        raise SystemExit('Refusing: requires local meal_connect_test database.')
    output.parent.mkdir(parents=True, exist_ok=True)
    password = 'QaAdmin-' + secrets.token_urlsafe(32) + '!'
    email = 'qa.meal215.admin.' + uuid4().hex + '@example.com'
    engine = get_engine()
    try:
        with Session(engine) as db:
            if db.scalar(text('SELECT current_database()')) != 'meal_connect_test':
                raise SystemExit('Database verification failed.')
            user = User(first_name='QA', last_name='Admin', email=email,
                        password_hash=hash_password(password), role=UserRole.admin,
                        account_status=AccountStatus.active)
            db.add(user)
            db.flush()
            # Create a NEW test account only; never promote an existing account.
            with output.open('x', encoding='utf-8') as handle:
                json.dump({'email': email, 'password': password}, handle, indent=2)
            try:
                db.commit()
            except BaseException:
                output.unlink(missing_ok=True)
                raise
        print('Created a dedicated QA admin in meal_connect_test.')
        print('Saved private Selenium configuration:', output)
        print('Do not commit or attach qa-admin.json to a report.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
