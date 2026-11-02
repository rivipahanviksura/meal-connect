
# Meal Connect Backend

FastAPI backend for the Meal Connect MVP.

## Technology
- Python
- FastAPI
- Uvicorn
- PostgreSQL (integration planned)

## Local Setup

Run these commands from the repository root.

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r backend/requirements.txt
```

### 4. Start the API

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

## API Endpoints

- Health: http://127.0.0.1:8000/api/v1/health
- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json

## Run Tests

From the backend directory:

```powershell
python -m pytest -q
```

## Frontend Integration

The Angular frontend runs at http://localhost:4200.

A development proxy forwards requests beginning with `/api/` to the FastAPI backend at http://127.0.0.1:8000.

## Current Scope

Implemented:
- FastAPI application foundation
- Versioned API router
- Health endpoint
- Local CORS configuration
- Health endpoint automated test

Pending:
- PostgreSQL database integration
- Authentication and role-based authorization
- Organization and donation endpoints

The project uses localhost development without Docker.
