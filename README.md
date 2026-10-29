# Meal Connect

Team Apex — web-based surplus-food donation and distribution MVP.

## Repository layout

- `frontend/` — responsive HTML, CSS, JS and Bootstrap views.
- `backend/app/api/` — FastAPI REST routes.
- `backend/app/models/` — ORM models (planned).
- `backend/app/schemas/` — request/response validation schemas.
- `backend/app/services/` — business workflows.
- `backend/tests/` — backend tests.
- `database/` — database-related files and migration work (planned).
- `docs/architecture/` — MEAL-5, MEAL-61 and MEAL-62 documentation.
- `docs/requirements/` — MVP scope and requirements.
- `docs/wireframes/` — screen designs.

## Setup status

This is a folder structure starter for JIRA MEAL-161 only. API implementation, executable application setup, dependency files, authentication and configuration are not included. Baseline project files and secrets handling are planned for Sprint 2.

## Working agreement (proposal)

Use topic branches such as `feature/MEAL-161-repository-structure`, open a pull request, and have another team member review before merging to `main`. Do not commit `.env`, passwords or API keys.
