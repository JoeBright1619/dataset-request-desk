# Dataset Request Desk

A small internal tool for managing client dataset requests against a corpus of
robot teleoperation episodes. Replaces the spreadsheet workflow currently used
to track requests, assign episodes, and record delivery outcomes.

> **Status:** work in progress. See `PLAN.md` for the implementation plan and
> current progress. Sections below describe the intended system; features land
> phase by phase.

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL
- **Frontend:** React, TypeScript, Vite
- **Infra:** Docker, Docker Compose

---

## Overview

Clients submit dataset requests ("200 episodes of `pick_cups`, delivered by
March 15"). Operators fulfil those requests by selecting episodes from the
corpus, assigning them to the request, and delivering the dataset. Clients then
accept or reject the delivered set; a rejection returns the request to
`in_progress` for rework.

Episodes arrive via CSV. Requests move through a fixed state machine:

```
submitted → in_progress → delivered → accepted
                        ↘ rejected ↗
```

---

## Architecture

See `docs/ARCHITECTURE.md` for the full picture. In one sentence: the backend
is a single FastAPI process with a layered `api → services → repositories → db`
structure, one PostgreSQL database, and a React SPA that talks to it over
HTTP/JSON.

---

## Prerequisites

- Python 3.11+ (for running the backend and tests outside Docker)
- PostgreSQL 16+ with the `pgcrypto` extension available
- Poetry 2.0+

Docker Compose and the frontend startup flow are planned for later phases.

---

## Quick Start

From a clean clone, create a database named `dataset_request_desk`, then:

```bash
cp .env.example .env
cd backend
poetry install
poetry run alembic upgrade head
poetry run python -m app.cli seed-users
poetry run uvicorn app.main:app --reload
```

The backend starts at `http://localhost:8000`. Seed users are idempotent, so
running the seed command again creates no duplicates.

---

## Database & Migrations

Run migrations from `backend/` after setting `DATABASE_URL` in the root `.env`:

```bash
poetry run alembic upgrade head
```

To create a new migration during development:

```bash
poetry run alembic revision --autogenerate -m "add <thing>"
```

Every schema change goes through Alembic. See `GUIDE.md` §2 for the migration
rules.

To seed the initial users manually:

```bash
poetry run python -m app.cli seed-users
```

---

## Seed Credentials

The backend startup task and the manual seed command load these predefined
accounts from `seed/users.json`. **They are for local development only.** Edit
that file before deploying anywhere.

| Role | Email | Password |
|---|---|---|
| admin | `admin@example.com` | `admin123` |
| operator | `ops1@example.com` | `ops123` |
| operator | `ops2@example.com` | `ops123` |
| client | `client-a@example.com` | `client123` |
| client | `client-b@example.com` | `client123` |

Use different credentials in production.

---

## Tests

Backend:

```bash
cd backend
pytest
```

Most tests use FastAPI's TestClient and run without external dependencies. The
health readiness test does verify database connectivity; ensure your `.env` file
has a valid `DATABASE_URL`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/dataset_request_desk pytest
```

Frontend:

```bash
cd frontend
npm test
```

Tests are fast and deterministic. See `GUIDE.md` §7 for the testing principles.

---

## API Documentation

- **Contract:** `docs/API.md` — the canonical HTTP contract.
- **Interactive:** `http://localhost:8000/docs` — FastAPI's auto-generated
  Swagger UI, useful for exploring the API by hand.
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

All routes are versioned under `/api/v1`.

---

## Episode Import

Episodes come from a CSV file. Two entry points share one importer:

**API**

```bash
curl -X POST http://localhost:8000/api/v1/episodes/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@seed/episodes.csv"
```

Requires the `operator` or `admin` role.

**CLI**

```bash
docker compose exec backend python -m app.cli import-episodes seed/episodes.csv
```

Both paths return the same summary:

```json
{
  "imported": 312,
  "skipped_duplicates": 4,
  "invalid": 6,
  "errors": [
    { "row": 17, "reason": "missing robot_id", "raw": { "episode_id": "episode-00017" } }
  ],
  "errors_truncated": false
}
```

The import is **partially successful**: valid rows commit, invalid rows are
reported. Re-running the same file is safe — duplicates are skipped via the
unique `episode_id` constraint. See `docs/NOTES.md` (Key Decisions — CSV import
atomicity).

The seed CSV is imported automatically on first startup. To re-import manually,
use either command above.

---

## Analytics

```bash
curl "http://localhost:8000/api/v1/analytics?from=2026-02-01T00:00:00Z&to=2026-03-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

Returns three aggregations over the date range, all computed in the database:

- Episodes recorded per day, per robot.
- Request counts by status, plus the median `submitted → delivered` time.
- Top 5 task names by number of `good` episodes.

See `docs/API.md` §6.1 for the exact response shape, and `docs/NOTES.md`
(Scale) for what changes at ~5 million episodes.

---

## Assumptions

- **Single-tenant.** The system serves one company. No org-level isolation.
- **No password reset.** Users are created by an admin; passwords are set at
  creation. A reset flow is out of scope.
- **No rate limiting.** Login and refresh are unprotected against brute force.
  A gateway-level limiter is assumed in any real deployment.
- **Operators are trusted.** All operator actions are logged via the status
  history, but there is no additional approval step for delivery.
- **UTC everywhere.** All timestamps are stored and returned in UTC. Clients
  are responsible for display timezones.
- **`episode_id` is globally unique.** If the CSV contains two rows with the
  same `episode_id`, the second is treated as a duplicate and skipped.
- **`robot_id` and `operator_name` are strings, not entities.** There is no
  `robots` or `operators` table. These are descriptive values from the CSV.

---

## Limitations

- **No background jobs.** CSV import is synchronous and bounded. Anything
  long-running would need a worker, which is out of scope for this build.
- **Offset pagination was rejected.** List endpoints use keyset (cursor)
  pagination; backward navigation works but there is no "jump to page N."
- **No total counts on lists.** Returning a `COUNT(*)` alongside every page
  would defeat the purpose of keyset pagination. If the UI ever needs a count,
  it will need a separate endpoint.
- **Analytics is synchronous.** At very large date ranges the aggregation
  query takes seconds. A materialised view is documented in `docs/NOTES.md`
  (Scale) as the fix, but is not implemented.
- **No internationalisation.** The UI is English-only.
- **No audit UI.** `request_status_history` and `assignments` record who did
  what, when, but there is no screen that surfaces the audit trail.

---

## Stretch Feature

_Not yet implemented._ See `PLAN.md` Phase 10 for the decision gate and
`docs/NOTES.md` (Key Decisions) for the outcome.

---

## Project Docs

- `GUIDE.md` — engineering rules and conventions
- `PLAN.md` — implementation plan and current tracker
- `docs/ARCHITECTURE.md` — components, layering, cross-cutting concerns
- `docs/API.md` — HTTP contract
- `docs/DATA_MODEL.md` — schema, constraints, indexes
- `docs/NOTES.md` — design rationale, key decisions, security, scale

## Reviewer Smoke Test

A 5-minute script to verify all required features work correctly from a clean clone:

### Prerequisites
- Docker Desktop installed and running
- Git
- Basic command-line familiarity

### Steps
1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd dataset-request-desk
   ```

2. **Start all services**:
   ```bash
   docker compose up --build -d
   ```

3. **Wait for services to be ready** (approximately 30 seconds):
   ```bash
   # Backend health check
   curl -s http://localhost:8000/health
   
   # Frontend should be accessible
   curl -s http://localhost:8080
   ```

4. **Login as an operator**:
   - Open http://localhost:8080 in your browser
   - You should be redirected to the login page
   - Email: `ops1@example.com`
   - Password: `ops123`
   - Click "Sign in"

5. **Verify operator dashboard loads**:
   - You should see the "All Requests" view
   - No requests should be present initially (clean state)

6. **Create a test request as a client**:
   - Click on your profile icon in the top-right
   - Select "Logout"
   - Login as client-a:
     - Email: `client-a@example.com`
     - Password: `client123`
   - Click "New Request" button
   - Fill in the form:
     - Task name: `test_task_smoke`
     - Robot ID: `test_robot_001`
     - Episodes: `5`
   - Click "Submit Request"

7. **Verify request appears in operator view**:
   - Logout from client-a
   - Login as ops1 again
   - You should see the newly created request in the list
   - Status should be `submitted`

8. **Test request lifecycle**:
   - Click on the request to open the detail view
   - Click "Start Work" to move to `in_progress`
   - Click "Deliver" to move to `delivered`
   - Click "Accept" to move to `accepted` (terminal state)

9. **Verify analytics endpoint**:
   ```bash
   # Get an auth token (operator)
   TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"ops1@example.com","password":"ops123"}' | \
     jq -r '.access_token')
   
   # Call analytics endpoint
   curl -s -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8000/api/v1/analytics?from=2026-01-01T00:00:00Z&to=2026-12-31T23:59:59Z" | jq .
   ```
   Should return aggregations including your test request data.

10. **Clean up**:
    ```bash
    docker compose down -v
    ```

### Expected Results
- All steps complete without errors
- Request flows through all states: submitted → in_progress → delivered → accepted
- Analytics endpoint returns data
- No console errors in browser or backend logs

### Troubleshooting
- If services fail to start: `docker compose logs` to check output
- If authentication fails: verify you're using the correct seed credentials
- If analytics returns empty: ensure you waited for services to fully start
