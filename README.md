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

- Docker and Docker Compose (for the one-command startup)
- Python 3.11+ (for running the backend and tests outside Docker)
- Node 20+ (for running the frontend outside Docker)

Everything below assumes Docker Compose is available. Running outside Docker
is documented at the bottom of this section.

---

## Quick Start

From a clean clone:

```bash
docker compose up
```

That brings up:

- PostgreSQL on `localhost:5432`
- Backend on `localhost:8000` (migrations and seed run automatically on first
  boot)
- Frontend on `localhost:5173`

Open `http://localhost:5173` and log in with one of the seed credentials below.

The first startup imports `seed/episodes.csv`. Subsequent startups are
idempotent — no duplicate episodes, no duplicate users.

To reset the environment completely:

```bash
docker compose down -v
docker compose up
```

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

The first startup seeds one user per role. **These are for local development
only.** Override them via environment variables before deploying anywhere.

| Role     | Username   | Password         |
|----------|------------|------------------|
| admin    | `admin`    | `admin-password` |
| operator | `operator` | `operator-pass`  |
| client   | `client`   | `client-pass`    |

Change these in production. See `.env.example` for the variables.

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