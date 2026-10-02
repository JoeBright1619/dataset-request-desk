# Dataset Request Desk

A small internal tool for managing client dataset requests against a corpus of
robot teleoperation episodes. Replaces the spreadsheet workflow currently used
to track requests, assign episodes, and record delivery outcomes.

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

- Docker and Docker Compose (the recommended way to run everything)
- Python 3.11+ and Poetry 2.0+ (only if running the backend outside Docker)
- Node.js 18+ and npm (only if running the frontend outside Docker)

---

## Quick Start

From a clean clone:

```bash
cp .env.example .env
docker compose up --build -d
```

That brings up:

- PostgreSQL
- Backend on `http://localhost:8000` (migrations and seed run automatically)
- Frontend on `http://localhost:8080`

Wait ~30 seconds for services to be healthy, then open
`http://localhost:8080` and log in with one of the seed credentials below.

The first startup imports `seed/episodes.csv`. Subsequent startups are
idempotent — no duplicate episodes, no duplicate users.

To reset everything (database included):

```bash
docker compose down -v
docker compose up --build -d
```

---

## Frontend Development

The frontend is a React + TypeScript app built with Vite. It talks to the
backend over HTTP/JSON.

### Running outside Docker

```bash
cd frontend
npm install
npm run dev
```

Serves at `http://localhost:3000`.

### Building

```bash
cd frontend
npm run build
```


### Environment Variables

Create `frontend/.env` if the backend is not on the default URL:

```
VITE_API_URL=http://localhost:8000/api/v1
```

The dev server proxies API calls to the backend; no CORS configuration is
needed for local development.

---

## Database & Migrations

Migrations run automatically on backend startup inside the Compose stack. To
run them manually against a running database:

```bash
docker compose exec backend alembic upgrade head
```

To create a new migration during development:

```bash
docker compose exec backend alembic revision --autogenerate -m "add <thing>"
```

Every schema change goes through Alembic. See `GUIDE.md` §2 for the migration
rules.

---

## Seed Credentials

Seed users are loaded from `seed/users.json` on startup. **They are for local
development only.** Edit that file before deploying anywhere.

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

Most tests use FastAPI's `TestClient` and run without external dependencies.
The health readiness test verifies database connectivity, so ensure
`DATABASE_URL` points at a running Postgres:

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
  Swagger UI.
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

All routes are versioned under `/api/v1`.

---

## Episode Import

Episodes come from a CSV file. Two entry points share one importer.

**API**

```bash
curl -X POST http://localhost:8000/api/v1/episodes/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@seed/episodes.csv"
```

Requires the `operator` or `admin` role.

**CLI (Docker Compose)**

```bash
docker compose exec backend python -m app.cli import-episodes seed/episodes.csv
```

**CLI (local backend)**

```bash
cd backend
poetry run python -m app.cli import-episodes seed/episodes.csv
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
unique `episode_id` constraint. See `docs/NOTES.md` for the import atomicity
decision.

The seed CSV is imported automatically on first startup. To re-import manually,
use any command above.

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

- **Single-tenant.** The system serves one company. `organisation` on users is
  a descriptive field, not a tenant key.
- **No password reset.** Users are created by an admin; passwords are set at
  creation.
- **No rate limiting.** Login and refresh are unprotected against brute force.
  A gateway-level limiter is assumed in any real deployment.
- **Operators are trusted.** All operator actions are logged via the status
  history, but there is no additional approval step for delivery.
- **UTC everywhere.** All timestamps are stored and returned in UTC. Clients
  are responsible for display timezones.
- **`episode_id` is globally unique.** A duplicate in the CSV is skipped.
- **`robot_id` and `operator_name` are strings, not entities.** There is no
  `robots` or `operators` table; these are descriptive values from the CSV.

---

## Limitations

- **No background jobs.** CSV import is synchronous and bounded.
- **Keyset pagination, no page numbers.** List endpoints use cursors with
  backward and forward navigation, but no "jump to page N."
- **No total counts on lists.** A `COUNT(*)` alongside every page would defeat
  keyset pagination.
- **Analytics is synchronous.** At very large date ranges the aggregation
  query takes seconds. A materialised view is the documented fix, not
  implemented.
- **No internationalisation.** The UI is English-only.
- **No audit UI.** `request_status_history` and `assignments` record who did
  what, when, but there is no screen that surfaces the audit trail.

---

## Stretch Feature

_Not implemented._ See `PLAN.md` Phase 10 for the decision gate and
`docs/NOTES.md` for the outcome.

---

## Project Docs

- `GUIDE.md` — engineering rules and conventions
- `PLAN.md` — implementation plan and current tracker
- `docs/ARCHITECTURE.md` — components, layering, cross-cutting concerns
- `docs/API.md` — HTTP contract
- `docs/DATA_MODEL.md` — schema, constraints, indexes
- `docs/NOTES.md` — design rationale, key decisions, security, scale

---

## Reviewer Smoke Test

A 5-minute script to verify all required features work end-to-end from a clean
clone. Assumes Docker Compose is running (`docker compose up --build -d`).

**1. Confirm services are healthy.**

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/health/ready
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080
```

Expect `{"status":"ok"}`, `{"status":"ready",...}`, and `200`.

**2. Log in as an operator.** Open `http://localhost:8080`, sign in as
`ops1@example.com` / `ops123`. Confirm the "All Requests" view loads.

**3. Log in as a client and create a request.** Log out, sign in as
`client-a@example.com` / `client123`. Click "New Request", fill in:

- Task name: `test_task_smoke`
- Episodes requested: `5`
- Deadline: any future date

Submit. Confirm it appears in the client's list with status `submitted`.

**4. Fulfil the request as an operator.** Log out, sign in as `ops1` again.
Open the new request. Click "Start Work" → status becomes `in_progress`.

**5. Assign episodes.** In the request detail view, click "Assign episodes to
this request". Search for episodes matching `test_task_smoke` (or any `good` /
`usable` episodes if none match). Select enough to meet the requested count.
Confirm the assigned count updates on the request.

**6. Deliver the request.** Back on the request detail view, click "Deliver".
Status becomes `delivered`.

**7. Accept as the client.** Log out, sign in as `client-a`. Open the request.
Click "Accept". Status becomes `accepted` (terminal).

**8. Verify analytics.**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ops1@example.com","password":"ops123"}' | jq -r '.access_token')

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/analytics?from=2026-01-01T00:00:00Z&to=2026-12-31T23:59:59Z" | jq .
```

Expect aggregations that include the request you just processed.

**9. Clean up.**

```bash
docker compose down -v
```

### Expected results

- All steps complete without errors.
- The request flows `submitted → in_progress → delivered → accepted`.
- The analytics endpoint returns data including the test request.
- No console errors in the browser or backend logs.

### Troubleshooting

- **Services fail to start:** `docker compose logs` to inspect output.
- **Authentication fails:** verify you are using the seed credentials from the
  table above.
- **Analytics returns empty:** wait a few more seconds for startup to finish,
  then retry.