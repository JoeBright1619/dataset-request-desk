# Implementation Plan

Working schedule for the Dataset Request Desk build. This file is the
schedule. Rules live in `GUIDE.md`; contract lives in `docs/API.md`; schema
lives in `docs/DATA_MODEL.md`; rationale lives in `docs/NOTES.md`.

## How to Use This File

- Only one task is `IN PROGRESS` at a time. Update the CURRENT TASK block when
  you start and finish one.
- Mark a task complete only after its acceptance criteria are verified (test or
  manual run — not "the code looks right").
- Update `CURRENT TASK` and `PROJECT PROGRESS` in the same commit as the work.
- Every phase ends with two mandatory tail tasks: `T1` (phase tests) and `D1`
  (phase docs sync). A phase is not complete until both are ticked.
- If a task runs past 2× its estimate, stop and see `docs/GUIDE.md` §11.

## MVP Bar

Mandatory for the assessment: Phases 1–9, 11. Phase 10 (stretch) is optional
and only starts once 1–9 are complete, tested, and documented.

---

# CURRENT TASK

TASK-04-04 — EpisodeImportService

Status: Not Done


---

# PROJECT PROGRESS

- [x] Phase 1 — Foundation
- [x] Phase 2 — Database & migrations
- [x] Phase 3 — Authentication & authorization
- [ ] Phase 4 — Episodes & CSV import
- [ ] Phase 5 — Requests & state machine
- [ ] Phase 6 — Assignments
- [ ] Phase 7 — Analytics
- [ ] Phase 8 — Frontend
- [ ] Phase 9 — Observability & Docker
- [ ] Phase 10 — Stretch feature (optional)
- [ ] Phase 11 — Final review

---

## Phase 1 — Foundation

Establish the repo skeleton, the backend and frontend scaffolds, the shared
configuration surface, and the doc set that every later phase will update.

- [x] TASK-01-01 — Initialize repository skeleton

  Objective:
  Create the top-level repo layout and initial docs.

  Implementation:
  - Create directories: `backend/`, `frontend/`, `docs/`, `seed/`.
  - Create `README.md`, `GUIDE.md`, and `docs/` stubs.
  - Add `.gitignore` covering Python, Node, `.env`, IDE files.
  - Add `.env.example` with placeholder keys (database URL, JWT secret,
    CORS origins).

  Acceptance criteria:
  - Repo has the expected top-level layout.
  - `.env` is gitignored; `.env.example` is committed.
  - No secrets in any committed file.

  Files:
  - `.gitignore`, `.env.example`, `README.md`, `GUIDE.md`, `docs/`

  Commit:
  chore(repo): initialize project skeleton and docs

- [x] TASK-01-02 — Backend package layout and FastAPI bootstrap

  Objective:
  Scaffold the backend with the layered layout described in
  `docs/ARCHITECTURE.md` §3.

  Implementation:
  - Create `backend/app/{api,core,models,schemas,services,repositories,db,cli}`
    with `__init__.py` files.
  - `app/main.py` assembles the FastAPI app, mounts the versioned router
    prefix `/api/v1`, and registers exception handlers.
  - `app/core/config.py` loads settings from env via Pydantic Settings and
    fails fast on missing required values.
  - Add `pyproject.toml` (or `requirements.txt`) with FastAPI, Pydantic,
    SQLAlchemy 2.x, Alembic, Pydantic Settings, uvicorn, bcrypt, pyjwt,
    pytest.

  Acceptance criteria:
  - `uvicorn app.main:app` starts without errors.
  - Missing required env var causes a clear startup failure.
  - `/api/v1` prefix is applied to routers.

  Files:
  - `backend/app/main.py`, `backend/app/core/config.py`, `backend/pyproject.toml`

  Commit:
  feat(backend): bootstrap FastAPI app with layered layout

- [x] TASK-01-03 — Error hierarchy and exception handlers

  Objective:
  Implement the single error envelope described in `docs/API.md` §0.4.

  Implementation:
  - `app/core/errors.py` defines `AppError` and subclasses
    (`NotFoundError`, `ForbiddenError`, `InvalidTransitionError`, etc.) with
    `code`, `message`, `http_status`, `field`.
  - Register FastAPI exception handlers to render `AppError` and override the
    default `RequestValidationError` handler so validation errors match the
    same envelope.

  Acceptance criteria:
  - Raising an `AppError` produces the documented JSON shape.
  - Pydantic validation failures render the same envelope with code
    `VALIDATION_ERROR`.
  - Stack traces never appear in any response.

  Files:
  - `backend/app/core/errors.py`, `backend/app/main.py`

  Commit:
  feat(core): add structured error envelope and handlers

- [x] TASK-01-04 — Structured logging middleware

  Objective:
  Emit one structured log line per request, per `GUIDE.md` §5.

  Implementation:
  - Configure a JSON logger in `app/core/logging.py`.
  - Add middleware emitting `method`, `path`, `status`, `duration_ms`,
    `user_id` (when authenticated).
  - Ensure sensitive headers and bodies are never logged.

  Acceptance criteria:
  - Every request produces exactly one log line.
  - `Authorization` header and request bodies are absent from logs.
  - Logs are valid JSON per line.

  Files:
  - `backend/app/core/logging.py`, `backend/app/main.py`

  Commit:
  feat(core): add structured request logging middleware

- [x] TASK-01-05 — Health endpoints

  Objective:
  Implement `/health` (liveness) and `/health/ready` (readiness) per
  `docs/API.md` §7.

  Implementation:
  - `/health` returns `{ "status": "ok" }` without touching the database.
  - `/health/ready` runs a `SELECT 1` with a short timeout and returns 200 or
    503 per `docs/API.md`.

  Acceptance criteria:
  - `/health` returns 200 with database down.
  - `/health/ready` returns 503 with database down, 200 with it up.
  - No credentials or connection strings in either response.

  Files:
  - `backend/app/api/health.py`

  Commit:
  feat(health): add liveness and readiness endpoints

- [x] TASK-01-06 — Frontend scaffold

  Objective:
  Scaffold the React + TypeScript app. Deliberately minimal.

  Implementation:
  - Vite + React + TypeScript.
  - A single `api/client.ts` with a fetch wrapper that attaches the bearer
    token and unwraps the error envelope.
  - Placeholder pages for login, requests, episodes.
  - No design system, no animations.

  Acceptance criteria:
  - `npm run dev` serves a page.
  - The API client attaches the `Authorization` header when a token exists.
  - The API client surfaces `error.code` from failed calls.

  Files:
  - `frontend/`

  Commit:
  chore(frontend): scaffold React + TypeScript app

- [x] TASK-01-T1 — Phase tests

  Objective:
  Cover the foundation: config fail-fast, error envelope, health behaviour.

  Implementation:
  - Test that a missing required env var raises at startup.
  - Test the error envelope shape for a raised `AppError` and for a Pydantic
    validation failure.
  - Test `/health` and `/health/ready` with the database up.

  Acceptance criteria:
  - `pytest` passes from a clean state (17 tests).
  - Tests are organized by domain: config, error envelope, health.
  - Config validation tests verify fail-fast behavior.
  - Error envelope tests verify both AppError and Pydantic validation errors.
  - Health tests verify liveness/readiness behavior and credential safety.

  Files:
  - `backend/tests/conftest.py`
  - `backend/tests/__init__.py`
  - `backend/tests/test_config.py` (5 tests)
  - `backend/tests/test_error_envelope.py` (7 tests)
  - `backend/tests/test_health.py` (5 tests)

  Commit:
  test(foundation): cover config, errors, and health

- [x] TASK-01-D1 — Phase docs sync

  Objective:
  Confirm the doc set matches what was built.

  Implementation:
  - Update `README.md` prerequisites and dev run instructions.
  - Confirm `GUIDE.md` and `docs/ARCHITECTURE.md` reflect the directories
    actually created.
  - Confirm `docs/API.md` §7 matches the health endpoints.
  - Update `PLAN.md` trackers.

  Acceptance criteria:
  - A clean clone can run the backend by following `README.md`.
  - No dangling references in any doc.

  Commit:
  docs(foundation): sync README and architecture with Phase 1

---

## Phase 2 — Database & migrations

Introduce PostgreSQL, SQLAlchemy models, and Alembic. Seed users come later.

- [x] TASK-02-01 — Database engine, session, and base

  Objective:
  Provide the `db` layer described in `docs/ARCHITECTURE.md` §2.

  Implementation:
  - `app/db/engine.py` builds the SQLAlchemy engine from settings.
  - `app/db/session.py` provides a request-scoped session and a transaction
    context manager.
  - `app/db/base.py` exposes `Base` for all models.

  Acceptance criteria:
  - Session dependency yields one session per request.
  - Exception inside the request rolls back the transaction.
  - Success commits.

  Files:
  - `backend/app/db/`

  Commit:
  feat(db): add engine, session, and transaction boundaries

- [x] TASK-02-02 — Models for all six tables

  Objective:
  Define the SQLAlchemy models matching `docs/DATA_MODEL.md`.

  Implementation:
  - `User`, `Episode`, `Request`, `Assignment`, `RequestStatusHistory`,
    `RefreshToken`.
  - All constraints from `docs/DATA_MODEL.md` §2: unique, check, FK, and the
    **partial unique index on `assignments(episode_id) WHERE released_at IS
    NULL`**.
  - All indexes from `docs/DATA_MODEL.md` §5.

  Acceptance criteria:
  - Models import cleanly. ✓
  - The partial unique index is declared on the model. ✓
  - All 6 tables registered in Base.metadata. ✓
  - All check constraints (role, status, quality, duration) present. ✓
  - All keyset pagination indexes (4 on episodes, 3 on requests, etc.) present. ✓
  - Passes ruff linting and formatting checks. ✓

  Files:
  - `backend/app/models/__init__.py`
  - `backend/app/models/user.py`
  - `backend/app/models/episode.py`
  - `backend/app/models/request.py`
  - `backend/app/models/assignment.py`
  - `backend/app/models/request_status_history.py`
  - `backend/app/models/refresh_token.py`

  Commit:
  feat(models): define schema for users, episodes, requests, assignments, history, tokens

- [x] TASK-02-03 — Alembic setup and initial migration

  Objective:
  Configure Alembic and generate the initial migration.

  Implementation:
  - `alembic.ini`, `migrations/env.py` reading the URL from settings.
  - One initial migration creating all tables and indexes.
  - Verify the partial unique index is present in the migration.

  Acceptance criteria:
  - `alembic upgrade head` from empty DB succeeds. ✓
  - `alembic downgrade base` then `upgrade head` succeeds. ✓
  - The partial unique index appears in `\d assignments` in `psql`. ✓
  - Migration file: `08ab3cf702b8_initial_schema.py`
  - Partial unique index definition: `CREATE UNIQUE INDEX ix_assignments_episode_id_active ON public.assignments USING btree (episode_id) WHERE (released_at IS NULL)` ✓
  - All check constraints (role, quality, duration, status) present in migration. ✓
  - All keyset pagination indexes present in migration. ✓

  Files:
  - `backend/alembic.ini`
  - `backend/migrations/env.py`
  - `backend/migrations/script.py.mako`
  - `backend/migrations/versions/08ab3cf702b8_initial_schema.py`

  Commit:
  feat(db): add initial migration for the full schema

- [x] TASK-02-04 — Seed users (idempotent)

  Objective:
  Ensure seed users exist on startup based on `seed/users.json`.

  Implementation:
  - `app/services/seed_service.py` loads users from `seed/users.json` (5 users: 1 admin, 2 operators, 2 clients).
  - Schema uses `email` as unique identifier, includes `name` and `organisation`.
  - Called from a startup hook or a one-shot CLI command.
  - Credentials documented in `seed/users.json`.

  Acceptance criteria:
  - Running the seed twice does not create duplicates. ✓
  - Each role can be logged into (verified in Phase 3).
  - Seed service uses bcrypt for password hashing. ✓
  - CLI command: `python -m app.cli seed-users` works. ✓
  - Startup hook in app/main.py runs seed on application startup. ✓
  - Idempotency verified: 5 created first run, 0 created + 5 existing on second run. ✓

  Files:
  - `backend/app/services/seed_service.py`
  - `backend/app/cli/seed_users.py`
  - `backend/app/cli/__main__.py`
  - `backend/app/main.py` (added startup hook)
  - `docs/DATA_MODEL.md` (updated User schema to use email, name, organisation)
  - `docs/API.md` (updated login endpoint to use email)
  - `backend/migrations/versions/3caf820a0b4e_update_users_schema_to_use_email_name_.py`

  Commit:
  feat(seed): add idempotent seed users based on seed/users.json

- [x] TASK-02-T1 — Phase tests

  Objective:
  Verify the schema and seed behaviour.

  Implementation:
  - Test the partial unique index rejects a second active assignment.
  - Test the release-then-reassign path succeeds.
  - Test seed idempotency.

  Acceptance criteria:
  - All three tests pass against a real Postgres.
  - Removing the partial unique index breaks the first test.

  Files:
  - `backend/tests/test_schema.py`

  Commit:
  test(db): cover schema constraints and seed idempotency

- [x] TASK-02-D1 — Phase docs sync

  Objective:
  Confirm migration and seed instructions are documented.

  Implementation:
  - Update `README.md` with migration and seed commands.
  - Confirm `docs/DATA_MODEL.md` matches the migration (no drift).
  - Update `PLAN.md` trackers.

  Commit:
  docs(db): sync README and data model with Phase 2

---

## Phase 3 — Authentication & authorization

JWT access + refresh, role-based dependencies, and the object-level
authorization helper used by every later phase.

- [x] TASK-03-01 — Password hashing and JWT utilities

  Objective:
  Provide the security primitives.

  Implementation:
  - `app/core/security.py`: bcrypt hashing, JWT sign/verify.
  - Constants for access-token lifetime and refresh-token lifetime.

  Acceptance criteria:
  - `hash_password` / `verify_password` round-trip.
  - Signed JWTs decode with the expected claims.

  Commit:
  feat(auth): add password hashing and JWT utilities

- [x] TASK-03-02 — Refresh-token storage and rotation

  Objective:
  Store refresh tokens hashed, rotate on use, revoke on reuse.

  Implementation:
  - `RefreshTokenRepository`.
  - `AuthService.issue_tokens`, `AuthService.refresh`.
  - Reuse of a used token revokes the whole chain for that user.

  Acceptance criteria:
  - Rotation emits a new token and marks the old one used.
  - Reusing a used token revokes the chain.

  Commit:
  feat(auth): add refresh token rotation and revocation

- [x] TASK-03-03 — Auth endpoints

  Objective:
  Implement `POST /auth/login`, `/auth/refresh`, `/auth/logout`,
  `GET /auth/me` per `docs/API.md` §1.

  Acceptance criteria:
  - Login returns tokens and follows the envelope.
  - Login failure returns `401 INVALID_CREDENTIALS` with the same body for
    unknown user, inactive user, and wrong password.
  - `GET /auth/me` returns the user.

  Commit:
  feat(auth): add login, refresh, logout, and me endpoints

- [x] TASK-03-04 — Current-user and role dependencies

  Objective:
  Provide the FastAPI dependencies used by every protected route.

  Implementation:
  - `get_current_user` — validates bearer token, returns user.
  - `require_roles(...)` — factory returning a dependency that enforces role.

  Acceptance criteria:
  - Missing/invalid token returns `401 AUTHENTICATION_REQUIRED`.
  - Wrong role returns `403 FORBIDDEN`.

  Commit:
  feat(auth): add current-user and role dependencies

- [x] TASK-03-05 — Object-level authorization helper

  Objective:
  Standardise the "does this caller own this resource" check.

  Implementation:
  - Helper in `app/services/authorization.py` used by services.
  - Rule: non-visible resources raise `NotFoundError`, not `ForbiddenError`.

  Acceptance criteria:
  - Client requesting another client's resource gets `404`, not `403`.

  Commit:
  feat(auth): add object-level authorization helper

- [x] TASK-03-06 — User management endpoints

  Objective:
  Implement `GET/POST/GET/PATCH /users` per `docs/API.md` §2. Admin-only.

  Acceptance criteria:
  - Only admins can call any of these.
  - Admin cannot demote or deactivate themselves (`403 FORBIDDEN`).
  - Deactivation revokes refresh tokens.

  Commit:
  feat(users): add admin user management endpoints

- [x] TASK-03-T1 — Phase tests

  Objective:
  Cover authentication, role, and object-level authorization.

  Implementation:
  - Client cannot see another client's resources.
  - Client cannot perform operator actions.
  - Operator cannot perform admin actions.
  - Refresh rotation works; reuse revokes chain.
  - Deactivation revokes refresh tokens.

  Acceptance criteria:
  - All tests pass.
  - Removing any check breaks at least one test.

  Files:
  - `backend/tests/test_auth.py`, `backend/tests/test_authorization.py`

  Commit:
  test(auth): cover roles, ownership, and token rotation

- [x] TASK-03-D1 — Phase docs sync

  Objective:
  Confirm the auth contract in `docs/API.md` §1–2 matches the implementation.

  Implementation:
  - Verify error codes and status codes in `docs/API.md` match.
  - Update `README.md` seed credentials if they changed.
  - Update `PLAN.md` trackers.

  Commit:
  docs(auth): sync API contract and README with Phase 3

---

## Phase 4 — Episodes & CSV import

Episode domain, list and detail endpoints, and the shared import service.

- [x] TASK-04-01 — Episode repository

  Objective:
  Data access for episodes.

  Implementation:
  - List with cursor pagination (bidirectional), filters
    (`task_name`, `quality`, `robot_id`, `recorded_from`, `recorded_to`,
    `assigned`), fixed sort `(recorded_at DESC, episode_id DESC)`.
  - Get by domain `episode_id`.
  - Bulk insert with `ON CONFLICT (episode_id) DO NOTHING` for import.

  Acceptance criteria:
  - Cursor forward and backward produce correct pages.
  - Filter hash mismatch on cursor returns `400 INVALID_CURSOR`.

  Commit:
  feat(episodes): add repository with cursor pagination and filters

- [x] TASK-04-02 — Cursor pagination helper

  Objective:
  Reusable cursor encoder/decoder used by every list endpoint.

  Implementation:
  - Encode `{ sort_values, direction, filter_hash }` as base64 JSON.
  - Decode and validate; raise `INVALID_CURSOR` on malformed or hash mismatch.
  - Helper emits `next_cursor`, `prev_cursor`, `has_more`, `has_prev`.

  Acceptance criteria:
  - Forward and backward scans return rows in the same visual order.
  - Filter change between pages returns `400 INVALID_CURSOR`.

  Commit:
  feat(pagination): add bidirectional keyset cursor helper

- [x] TASK-04-03 — Episode endpoints

  Objective:
  Implement `GET /episodes` and `GET /episodes/{episode_id}` per
  `docs/API.md` §3.1–3.2.

  Acceptance criteria:
  - Operators and admins only.
  - Cursor envelope shape matches `docs/API.md`.
  - Unknown `episode_id` returns `404 NOT_FOUND`.

  Commit:
  feat(episodes): add list and detail endpoints

- [ ] TASK-04-04 — EpisodeImportService

  Objective:
  One shared importer used by API and CLI.

  Implementation:
  - Row-by-row parsing and validation.
  - Insert valid rows with `ON CONFLICT (episode_id) DO NOTHING`.
  - Return `{ imported, skipped_duplicates, invalid, errors[], errors_truncated }`.
  - `errors` capped at 100 entries.

  Acceptance criteria:
  - Running the same file twice inserts nothing new the second time.
  - Invalid rows are reported with row number and reason.
  - A row with a duplicate `episode_id` is reported as skipped, not as invalid.

  Commit:
  feat(episodes): add shared CSV import service

- [ ] TASK-04-05 — Import endpoints (API + CLI)

  Objective:
  Wire the service to `POST /episodes/import` and
  `python -m app.cli import-episodes <file>`.

  Acceptance criteria:
  - Both paths produce identical summaries for the same file.
  - File too large returns `400 IMPORT_ERROR`.
  - Missing `file` field returns `422 VALIDATION_ERROR`.

  Commit:
  feat(episodes): expose CSV import via API and CLI

- [ ] TASK-04-T1 — Phase tests

  Objective:
  Cover importer correctness, idempotency, and list behaviour.

  Implementation:
  - Valid records import.
  - Invalid records are reported with reason.
  - Duplicates are reported as skipped.
  - Running twice creates no new rows.
  - Cursor pagination forward and backward over a synthetic 1000-row set.
  - Filter changes between pages return `INVALID_CURSOR`.

  Acceptance criteria:
  - All tests pass against a real Postgres.
  - Removing `ON CONFLICT` breaks idempotency test.

  Files:
  - `backend/tests/test_import.py`, `backend/tests/test_episode_list.py`

  Commit:
  test(episodes): cover import and cursor pagination

- [ ] TASK-04-D1 — Phase docs sync

  Objective:
  Confirm import and pagination contracts match `docs/API.md`.

  Implementation:
  - Verify `docs/API.md` §3.1–3.3 matches the implementation.
  - Update `docs/DATA_MODEL.md` if any index changed.
  - Update `PLAN.md` trackers.

  Commit:
  docs(episodes): sync API and data model with Phase 4

---

## Phase 5 — Requests & state machine

Request creation, listing, detail, and the single status-transition endpoint.

- [ ] TASK-05-01 — Request repository

  Objective:
  Data access for requests and status history.

  Implementation:
  - List with cursor pagination, filters (`status`, `client_id`,
    `task_name`), sort `(created_at DESC, id DESC)`.
  - Client scoping enforced via a filter, not a separate query.
  - `create`, `get`, `update_status`, `append_history`.

  Commit:
  feat(requests): add repository with cursor pagination and scoping

- [ ] TASK-05-02 — Request domain service (create + read)

  Objective:
  Implement `POST /requests`, `GET /requests`, `GET /requests/{id}`.

  Acceptance criteria:
  - Only clients create requests.
  - Operators and admins see all; clients see only their own.
  - Request not visible → `404 NOT_FOUND`.

  Commit:
  feat(requests): add creation and read endpoints

- [ ] TASK-05-03 — Request state machine

  Objective:
  Implement the transition table and rules from `docs/API.md` Appendix A.

  Implementation:
  - Transition table as data: mapping
    `(from, to) → (required_role, extra_condition)`.
  - `RequestService.transition_status` re-reads the request with
    `SELECT ... FOR UPDATE`, checks the transition, checks the preconditions,
    updates `requests.status`, and writes a `request_status_history` row —
    all in one transaction.
  - `in_progress → delivered` requires `episodes_assigned >= episodes_requested`
    (using the count computed from `assignments`).

  Acceptance criteria:
  - All valid transitions succeed and write a history row.
  - Invalid transitions return `409 INVALID_STATUS_TRANSITION`.
  - Wrong role returns `403 FORBIDDEN`.
  - Insufficient episodes returns `409 INSUFFICIENT_EPISODES`.
  - Concurrent calls from the same starting status: exactly one succeeds.

  Commit:
  feat(requests): enforce status transitions with row lock

- [ ] TASK-05-04 — Status transition endpoint

  Objective:
  Implement `POST /requests/{id}/status` per `docs/API.md` §4.4.

  Acceptance criteria:
  - Response returns the full updated request.
  - `reason` is stored on the history row when provided.

  Commit:
  feat(requests): add status transition endpoint

- [ ] TASK-05-T1 — Phase tests

  Objective:
  Cover the state machine exhaustively.

  Implementation:
  - Every valid transition succeeds for the correct role.
  - Every invalid transition returns `409`.
  - Wrong role returns `403`.
  - `accepted` is terminal.
  - Delivery without enough episodes returns `409 INSUFFICIENT_EPISODES`.
  - Concurrent transitions serialize (one succeeds, the other fails).
  - Clients cannot see other clients' requests (`404`).

  Acceptance criteria:
  - All cases pass.
  - Removing the row lock breaks the concurrency test.

  Files:
  - `backend/tests/test_request_workflow.py`

  Commit:
  test(requests): cover workflow transitions and concurrency

- [ ] TASK-05-D1 — Phase docs sync

  Objective:
  Confirm the state machine in `docs/API.md` Appendix A matches the code.

  Commit:
  docs(requests): sync state machine and endpoint contract with Phase 5

---

## Phase 6 — Assignments

Assignment creation, listing, release, and the concurrency guarantee.

- [ ] TASK-06-01 — Assignment repository

  Objective:
  Data access for assignments.

  Implementation:
  - List active assignments for a request with cursor pagination, sort
    `(assigned_at DESC, episode_id DESC)`.
  - `assign_batch(request_id, episode_ids, user_id)`: attempts each insert,
    catches `IntegrityError` per row, and returns `(assigned, rejected)`.
  - `release(request_id, episode_id)` sets `released_at = now()`.

  Commit:
  feat(assignments): add repository with partial-unique-safe batch insert

- [ ] TASK-06-02 — Assignment endpoints

  Objective:
  Implement `GET/POST/DELETE /requests/{id}/assignments` per
  `docs/API.md` §5.

  Acceptance criteria:
  - Batch POST returns `{ assigned, rejected, episodes_requested,
    episodes_assigned }`.
  - Reasons are `not_found`, `invalid_quality`, `already_assigned`.
  - Whole request fails with `409 INVALID_STATUS_TRANSITION` if the request is
    not in `submitted` or `in_progress`.
  - DELETE returns `204` and marks released.

  Commit:
  feat(assignments): add list, assign, and release endpoints

- [ ] TASK-06-T1 — Phase tests

  Objective:
  Cover assignment rules exhaustively.

  Implementation:
  - `bad` episode cannot be assigned (per-episode rejection).
  - Already-assigned episode cannot be assigned again (per-episode rejection,
    HTTP still `200`).
  - Concurrent assignment of the same episode: exactly one succeeds, other is
    rejected with `already_assigned`.
  - Releasing then reassigning succeeds.
  - Delivery with insufficient episodes still blocked even after several
    successful assignments.
  - Delivery succeeds once enough episodes are assigned.

  Acceptance criteria:
  - All cases pass against a real Postgres.
  - Removing the partial unique index breaks the concurrency test.

  Files:
  - `backend/tests/test_assignments.py`

  Commit:
  test(assignments): cover rules and concurrency

- [ ] TASK-06-D1 — Phase docs sync

  Objective:
  Confirm the assignment contract matches the code.

  Commit:
  docs(assignments): sync API and data model with Phase 6

---

## Phase 7 — Analytics

Aggregations in the database. No Python-side computation over large sets.

- [ ] TASK-07-01 — AnalyticsRepository

  Objective:
  Implement the three aggregations from `docs/API.md` §6.1.

  Implementation:
  - `episodes_by_day_robot`: `GROUP BY DATE(recorded_at), robot_id`.
  - `requests_by_status`: `GROUP BY status`.
  - `median_submitted_to_delivered_hours`: `percentile_cont(0.5)` on
    `delivered_at - created_at` for requests delivered in range.
  - `top_tasks_by_good_episodes`: top 5 by count of `quality = 'good'`.

  Use SQLAlchemy Core or raw SQL, not the ORM. See
  `docs/ARCHITECTURE.md` §8.

  Acceptance criteria:
  - Each aggregation runs in a single query.
  - No full-table load into Python.

  Commit:
  feat(analytics): add aggregation repository

- [ ] TASK-07-02 — Analytics endpoint

  Objective:
  Implement `GET /analytics` per `docs/API.md` §6.1.

  Acceptance criteria:
  - Operators and admins only.
  - `from >= to` returns `422 VALIDATION_ERROR`.
  - Response matches the documented shape.

  Commit:
  feat(analytics): add analytics endpoint

- [ ] TASK-07-T1 — Phase tests

  Objective:
  Cover the aggregation correctness with small, deterministic fixtures.

  Implementation:
  - Known dataset produces known counts, medians, and top-N.
  - Empty range returns empty arrays and `null` for the median.
  - Non-operator gets `403`.
  - Invalid range returns `422`.

  Files:
  - `backend/tests/test_analytics.py`

  Commit:
  test(analytics): cover aggregations with deterministic fixtures

- [ ] TASK-07-D1 — Phase docs sync

  Objective:
  Confirm the analytics contract matches the code. Expand
  `docs/DATA_MODEL.md` §6 (Scale) if anything new surfaced.

  Commit:
  docs(analytics): sync contract and scale notes with Phase 7

---

## Phase 8 — Frontend

Keep it small. Functional correctness over polish.

- [ ] TASK-08-01 — Auth flow (login, token storage, guards)

  Objective:
  Login page, token storage, refresh on 401, and route guards by role.

  Acceptance criteria:
  - Login stores access + refresh tokens.
  - 401 triggers a refresh attempt once; on failure, redirects to login.
  - Routes are gated by role (client vs operator vs admin).

  Commit:
  feat(frontend): add auth flow and role-based routing

- [ ] TASK-08-02 — Client: requests page

  Objective:
  Client can create a request, view their list, see status, accept or reject
  a delivered request.

  Commit:
  feat(frontend): add client requests page

- [ ] TASK-08-03 — Operator: requests list and detail

  Objective:
  Operator sees all requests, inspects detail, transitions status.

  Commit:
  feat(frontend): add operator request list and detail

- [ ] TASK-08-04 — Operator: episode search and assignment

  Objective:
  Filter episodes by task, quality, robot, date, and assigned state.
  Assign and release episodes.

  Note: episode list uses cursor pagination. Navigation is "Prev / Next",
  not page numbers.

  Commit:
  feat(frontend): add episode search and assignment UI

- [ ] TASK-08-T1 — Phase tests

  Objective:
  Light tests on the API client and any non-trivial state.

  Implementation:
  - API client attaches `Authorization` and unwraps the error envelope.
  - Refresh-on-401 retries once and gives up cleanly.

  Acceptance criteria:
  - `npm test` passes.
  - No tests hit a real backend.

  Commit:
  test(frontend): cover API client and refresh behaviour

- [ ] TASK-08-D1 — Phase docs sync

  Objective:
  Update `README.md` with frontend dev instructions and note any UI
  simplifications in `docs/NOTES.md` (Simplifications).

  Commit:
  docs(frontend): sync README and notes with Phase 8

---

## Phase 9 — Observability & Docker

Make the system operable end-to-end from a clean clone.

- [ ] TASK-09-01 — Dockerfile (backend, frontend)

  Objective:
  Build images for backend and frontend.

  Acceptance criteria:
  - Backend image runs `uvicorn`.
  - Frontend image serves the built assets.

  Commit:
  chore(docker): add backend and frontend Dockerfiles

- [ ] TASK-09-02 — Docker Compose

  Objective:
  A clean clone runs with one command: `docker compose up`.

  Implementation:
  - Services: `db` (Postgres), `backend`, `frontend`.
  - Backend waits for `db` health, then runs `alembic upgrade head`, then
    seeds, then starts `uvicorn`.
  - Migrations and seed run as idempotent one-shots on startup.

  Acceptance criteria:
  - Fresh clone → `docker compose up` → working system at the documented URL.
  - Running again does not break or duplicate seed data.

  Commit:
  chore(docker): add compose stack with migrations and seed on startup

- [ ] TASK-09-03 — Seed CSV import on startup

  Objective:
  `seed/episodes.csv` is imported automatically on first boot.

  Acceptance criteria:
  - First `docker compose up` imports the CSV.
  - Subsequent runs do not duplicate episodes.

  Commit:
  chore(seed): import seed CSV on first startup

- [ ] TASK-09-04 — Operator smoke path

  Objective:
  A documented 5-minute script a reviewer can follow to exercise every
  required feature.

  Implementation:
  - Add a "Reviewer smoke test" section to `README.md`.

  Commit:
  docs(readme): add reviewer smoke test path

- [ ] TASK-09-T1 — Phase tests

  Objective:
  Verify the compose stack behaves idempotently.

  Implementation:
  - `docker compose up` twice in CI, assert no duplication.
  - Assert `/health/ready` returns 200 after boot.

  Commit:
  test(docker): verify compose idempotency and readiness

- [ ] TASK-09-D1 — Phase docs sync

  Objective:
  Full pass over `README.md` from a clean clone. Fix anything that requires
  guessing. Update `docs/NOTES.md` with any operational surprises.

  Commit:
  docs(ops): sync README and notes with Phase 9

---

## Phase 10 — Stretch feature (optional)

Only starts once Phases 1–9 are complete, tested, and documented.

- [ ] TASK-10-01 — Stretch decision gate

  Objective:
  Choose between Option A (real-time updates), Option B (background export
  jobs), Option C (deployment).

  Implementation:
  - Write a short section in `docs/NOTES.md` (Key Decisions) comparing the
    three against remaining time and existing architecture.
  - Only proceed if the required system is stable.

  Acceptance criteria:
  - Decision documented before implementation starts.
  - If no option is viable, tick this task and mark Phase 10 as skipped in the
    tracker, with a one-line reason in `docs/NOTES.md`.

  Commit:
  docs(stretch): record stretch feature decision

- [ ] TASK-10-02 — Implement chosen stretch feature

  Objective:
  Implement the chosen option at the smallest credible scope.

  (Detailed sub-tasks depend on choice; expand here when known.)

  Commit:
  feat(stretch): implement <chosen option>

- [ ] TASK-10-T1 — Phase tests

  Objective:
  Cover the stretch feature's behaviour and its failure modes.

  Commit:
  test(stretch): cover <chosen option>

- [ ] TASK-10-D1 — Phase docs sync

  Objective:
  Document the stretch feature in `README.md` and `docs/NOTES.md`.

  Commit:
  docs(stretch): document <chosen option>

---

## Phase 11 — Final review

Deliberate review of the whole system against the brief.

- [ ] TASK-11-01 — Domain review

  Objective:
  Walk through every domain rule from the brief and confirm enforcement.

  Checklist:
  - Status transitions enforced in service, row-locked.
  - `accepted` is terminal.
  - Assignment rules enforced (quality, exclusivity, status).
  - Delivery gated on sufficient episodes.
  - Client isolation (own requests only).
  - Role permissions (Appendix B in `docs/API.md`).

  Commit:
  chore(review): domain rules audit

- [ ] TASK-11-02 — Database review

  Objective:
  Verify schema integrity.

  Checklist:
  - `alembic upgrade head` from empty DB.
  - Constraints and indexes match `docs/DATA_MODEL.md`.
  - Analytics queries execute in the database (inspect logs / `EXPLAIN`).

  Commit:
  chore(review): database audit

- [ ] TASK-11-03 — Security review

  Objective:
  Confirm every security item in `GUIDE.md` §4 is honoured.

  Checklist:
  - Passwords hashed, never logged.
  - Tokens rotated and revoked.
  - IDOR prevented (404, not 403).
  - Unknown request fields rejected.
  - No secrets in any committed file.

  Commit:
  chore(review): security audit

- [ ] TASK-11-04 — Operations review

  Objective:
  Confirm operability.

  Checklist:
  - `docker compose up` from clean clone works.
  - `/health` and `/health/ready` behave per `docs/API.md`.
  - One structured log line per request; no secrets.
  - Seed users documented.

  Commit:
  chore(review): operations audit

- [ ] TASK-11-05 — Documentation review

  Objective:
  Confirm the docs match the system and the brief.

  Checklist:
  - `README.md` accurate from clean clone.
  - `GUIDE.md` consistent with what was built.
  - `docs/API.md`, `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md`,
    `docs/NOTES.md` mutually consistent and free of dangling references.
  - `docs/NOTES.md` covers Design, Simplifications, Something Went Wrong,
    Security, Scale, AI Tooling, and Key Decisions.

  Commit:
  chore(review): documentation audit

- [ ] TASK-11-06 — Git review

  Objective:
  Confirm commit history reflects the work.

  Checklist:
  - Commit messages meaningful.
  - No secrets, no generated files, no IDE files in the tree.
  - No monolithic "everything" commit.

  Commit:
  (no commit — this is a check)

- [ ] TASK-11-T1 — Final end-to-end test run

  Objective:
  Run the full test suite and the reviewer smoke path.

  Acceptance criteria:
  - `pytest` passes.
  - Reviewer smoke path from `README.md` completes.
  - `docker compose up` works from a fresh clone.

  Commit:
  chore(review): final end-to-end verification

- [ ] TASK-11-D1 — Final docs and tracker sync

  Objective:
  Confirm all trackers reflect reality. Mark `PROJECT PROGRESS` fully checked
  for mandatory phases. Clear `CURRENT TASK`.

  Commit:
  docs(review): final tracker sync
