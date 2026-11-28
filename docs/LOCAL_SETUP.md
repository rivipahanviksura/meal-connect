
# Meal Connect – Local Development Setup Guide

**Jira Task:** MEAL-33

**Project:** Meal Connect MVP

**Environment:** Windows Localhost (No Docker)

## 1. Overview

This guide explains how team members can set up and run the Meal Connect application locally.

Technology stack:
- Frontend: Angular 21, TypeScript, SCSS
- Backend: Python 3.14.3, FastAPI
- Database: PostgreSQL 17
- Frontend IDE: WebStorm
- Backend IDE: PyCharm
- Database Client: DBeaver
- API Testing: Postman
- Version Control: Git and GitHub

The frontend and backend can currently communicate through the Angular development proxy.

PostgreSQL is installed and accessible through DBeaver. Database migrations and FastAPI database integration are separate implementation tasks.

## 2. Prerequisites

Install and configure:
- Git
- Node.js and npm compatible with Angular 21
- Python compatible with the installed FastAPI dependencies
- PostgreSQL 17
- WebStorm
- PyCharm
- DBeaver
- Postman

Check installed tools:

```powershell
git --version
node --version
npm --version
python --version
```

## 3. Clone the Repository

Open PowerShell in your preferred projects folder:

```powershell
git clone https://github.com/rivipahanviksura/meal-connect.git
cd meal-connect
git switch develop
git pull --ff-only origin develop
```

Repository access is required because the project repository is private.

## 4. Repository Structure

```text
meal-connect/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
├── database/
├── docs/
├── frontend/
└── README.md
```

## 5. Frontend Setup – WebStorm

Open the repository in WebStorm.

Open a terminal in the repository root:

```powershell
cd frontend
npm ci
npm start
```

Open:

http://localhost:4200

Expected result:
- Meal Connect application loads
- Home page is visible
- Header and footer render correctly

Run a build check:

```powershell
npm run build
```

The frontend uses an Angular development proxy to forward `/api/` requests to FastAPI at `127.0.0.1:8000`.

## 6. Backend Setup – PyCharm

Open the repository in PyCharm.

Create a Python virtual environment from the repository root:

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
python -m pip install -r backend/requirements.txt
```

Run the backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

The API should run at:

http://127.0.0.1:8000

Check the health endpoint:

http://127.0.0.1:8000/api/v1/health

Expected JSON response:

```json
{
  "status": "ok",
  "service": "meal-connect-api"
}
```

Swagger API documentation:

http://127.0.0.1:8000/docs

## 7. PostgreSQL and DBeaver

Start the PostgreSQL server.

Open DBeaver and create or select a PostgreSQL connection.

Typical local settings:

| Setting | Value |
|---|---|
| Host | localhost |
| Port | 5432 |
| Initial database | postgres |
| Username | Your configured PostgreSQL user |
| Password | Your locally configured password |

Click **Test Connection**.

Expected result: Connection successful.

Do not commit database passwords or other credentials to GitHub.

The application-specific database schema and migrations will be configured under separate database implementation tasks.

## 8. API Testing – Postman

Ensure the FastAPI server is running.

Open Postman and create a new HTTP request:

- Method: GET
- URL: http://127.0.0.1:8000/api/v1/health

Click **Send**.

Expected:
- HTTP 200 OK
- JSON response containing `"status": "ok"`

## 9. Frontend–Backend Integration

Run both applications in separate terminals.

Frontend:

```powershell
cd frontend
npm start
```

Backend (from repository root, with the virtual environment activated):

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Open:

http://localhost:4200/api/v1/health

Expected response:

```json
{
  "status": "ok",
  "service": "meal-connect-api"
}
```

This verifies that the Angular development proxy can forward requests to FastAPI.

## 10. Automated Backend Testing

From the backend folder, with the virtual environment activated:

```powershell
python -m pytest -q
```

The initial health endpoint test should pass.

## 11. Git Workflow

The `main` branch contains stable project code.

The `develop` branch is the integration branch.

Create a feature branch from an updated `develop`:

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/MEAL-XXX-task-name
```

Commit and push changes, then create a pull request targeting `develop`.

Do not commit virtual environments, secrets, generated build files, or local database credentials.

## 12. Troubleshooting

### Frontend does not start
- Check Node.js and npm versions.
- Run `npm ci` inside `frontend`.
- Check whether port 4200 is already in use.

### Backend does not start
- Check that the correct Python virtual environment is active.
- Ensure dependencies are installed.
- Run Uvicorn from the `backend` directory.
- Check whether port 8000 is already in use.

### Proxy request fails
- Confirm FastAPI is running.
- Confirm the proxy configuration points to port 8000.
- Restart the Angular development server after changing proxy settings.

### PostgreSQL connection fails
- Check the PostgreSQL service status.
- Verify hostname, port, username, and password.
- Confirm the database server accepts local connections.

## 13. Current Limitations

Verified:
- Angular frontend runs locally
- FastAPI backend runs locally
- API health endpoint works
- Angular proxy connects to FastAPI
- PostgreSQL is reachable through DBeaver
- Postman health request returns HTTP 200
- Automated backend health test passes

Not yet verified:
- FastAPI to PostgreSQL connectivity
- Database migrations and seed data
- Authentication and role-based authorization
- Clean setup performed independently by another team member

## 14. Team Setup Verification

A teammate should clone the repository and independently follow this guide.

Record:
- Tester
- Test date
- Operating system and relevant software versions
- Frontend run result
- Backend run result
- PostgreSQL connection result
- Postman health test result
- Any setup issues and fixes

MEAL-33 should be marked complete only after the instructions have been successfully followed by a teammate, with results recorded in Jira.

## PostgreSQL Database Setup

Meal Connect uses PostgreSQL 17, SQLAlchemy, Alembic and Psycopg for local database development.

### Prerequisites

- PostgreSQL 17 installed and running
- Python virtual environment activated
- Backend dependencies installed
- Local database credentials available

### 1. Create the Local Database

Create a PostgreSQL database named `meal_connect` using DBeaver or another PostgreSQL administration tool.

```sql
CREATE DATABASE meal_connect;
```

Skip this command if the database already exists. Do not delete or overwrite an existing database.

### 2. Configure Environment Variables

Copy `backend/.env.example` to `backend/.env`.

Update `DATABASE_URL` with your local PostgreSQL connection information.

Example:

```dotenv
DATABASE_URL=postgresql+psycopg://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:5432/meal_connect
```

Never commit `.env` or real credentials to Git.

### 3. Install Backend Dependencies

From the project root:

```powershell
cd backend
python -m pip install -r requirements.txt
```

### 4. Apply Database Migrations

From the `backend` directory:

```powershell
python -m alembic upgrade head
```

Verify the revision:

```powershell
python -m alembic current
```

Expected initial revision: `d99d12936307`.

### 5. Load Fictional Development Data

For local development only:

```powershell
python -m scripts.seed_dev --confirm-development
```

The seed script creates fictional, disabled demo users, sample organizations, organization memberships and a sample food donation.

The demo user accounts are not usable for authentication.

The script may be run again without creating duplicate demo records.

Never run development seed data against production or a database containing real user information.

### 6. Verify Database Tables

Open DBeaver and connect to the `meal_connect` database.

Navigate to:

`Schemas → public → Tables`

The database should contain 10 application tables and the Alembic migration tracking table, `alembic_version`.

### 7. Run Backend Tests

```powershell
python -m pytest
```

### Important Notes

- Each team member maintains a separate local PostgreSQL database.
- GitHub stores the SQLAlchemy models, migration files and seed script, not the PostgreSQL database itself.
- Database schema changes must be introduced through Alembic migrations.
- Never edit or delete an already shared migration without team coordination.
- The initial schema supports future workflows; authentication, authorization and transaction-safe donation approval must still be implemented separately.
