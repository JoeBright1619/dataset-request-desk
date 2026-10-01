# Guide

Engineering rules for anyone working on this repository. This file is
**conventions and rules**, not facts about the current system. Facts live in
the docs listed below.

Read this before writing code. Re-read it before opening a PR.

---

## Referenced Documents

- `docs/API.md` — canonical HTTP contract: endpoints, shapes, status codes.
- `docs/DATA_MODEL.md` — canonical schema: tables, columns, constraints, indexes.
- `docs/ARCHITECTURE.md` — canonical layering, dependency direction, cross-cutting concerns.
- `docs/NOTES.md` — design rationale, key decisions, scale notes, what went wrong.

**Precedence rule.** If code and a doc disagree, the code is wrong until proven
otherwise. Update the doc in the same commit as the code change. No "doc later."

**One canonical home per fact.** Endpoint shapes live in `API.md` only. Column
constraints live in `DATA_MODEL.md` + migrations only. Reasoning lives in
`NOTES.md` only. Do not duplicate.

---

## 1. Architecture Principles

See `ARCHITECTURE.md` for the full picture. The rules:

- **Layering is `api → services → repositories → db`.** Dependencies point
  inward only. Never import across layers in the opposite direction.
- **Business rules live in `services`.** Not in routes, not in repositories,
  not in SQL triggers.
- **Route handlers do three things:** parse input, call one service method,
  format the response. No branching on domain rules.
- **Repositories translate between domain objects and SQL.** No business logic.
- **One service method = one transaction.** The outermost service method
  commits. Nested services do not. Repositories never commit.
- **Row locks where a read-then-write must be serialized.** Status transitions
  and assignment operations are the current examples.
- **Errors are structured.** Services raise `AppError` subclasses; one FastAPI
  handler renders them into the envelope in `API.md` §0.4. Never return raw
  exceptions to a client.
- **Validation is two-layered.** Pydantic validates shape at the HTTP
  boundary. Services validate domain rules that require state. They are
  complementary, not redundant.

---

## 2. Database Principles

- **Model relationally.** Foreign keys where the relationship is real. Do not
  add a lookup table unless the domain requires managing that entity.
- **Enforce invariants in the database where they must survive concurrency.**
  The two current examples:
  - `UNIQUE(episode_id)` on `episodes` — import idempotency.
  - Partial unique index on `assignments(episode_id) WHERE released_at IS NULL`
    — assignment exclusivity.
- **Add check constraints for enums and numeric ranges.** Application checks
  are a convenience; the database is the guarantee.
- **Index for the queries you actually run.** Every index in
  `DATA_MODEL.md` §5 exists because a specific query needs it. Do not add
  speculative indexes.
- **No N+1 queries.** If a loop issues a query per iteration, rewrite it as a
  join, an `IN`, or a single aggregated query. Inspect generated SQL when in
  doubt.
- **Paginate in the database.** Never load a full table into Python and slice.
- **Aggregate in the database.** Counts, sums, medians, and top-N run in SQL,
  not in Python.
- **Migrations.**
  - Every schema change goes through Alembic. No manual DDL, ever.
  - One migration per logical change.
  - Migrations must be reversible, or explicitly marked irreversible with a
    comment explaining why.
  - Data migrations (backfills) are separate from schema migrations.
  - Never edit a committed migration. Correct with a new migration.

---

## 3. API Principles

- **All responses are JSON objects.** Never bare arrays.
- **Success returns the resource directly.** No `data` wrapper.
- **Lists use the pagination envelope** in `API.md` §0.3.
- **Errors use the envelope** in `API.md` §0.4. Never return a bare string or
  a raw FastAPI validation error.
- **Use correct HTTP status codes.** See `API.md` §0.5. Do not default to
  `200` for everything.
- **Enforce authorization on the server.** The frontend hiding a button is UX,
  not security.
- **Two authorization checkpoints:**
  1. Route-level role check (FastAPI dependency).
  2. Object-level ownership check inside the service, after the resource is
     loaded.
- **Return `404` for not-visible resources**, not `403`. A `403` leaks
  existence.
- **Reject unknown fields** in request bodies (Pydantic `extra="forbid"`).
- **Never leak internals.** No stack traces, no SQL, no table names, no
  credential hints in any error response.
- **Version the API.** All routes under `/api/v1`. Breaking changes require a
  new prefix and an entry in `API.md`.

---

## 4. Security

- **Passwords.** Hashed with bcrypt. Plaintext never persisted, never logged,
  never echoed. Password fields are `repr`-excluded on Pydantic models.
- **Tokens.** Access tokens are short-lived JWTs. Refresh tokens are opaque,
  stored hashed, rotated on use, revoked on reuse. The `Authorization` header
  is never logged.
- **Authorization is server-side, at both checkpoints.** Role and object.
- **Input validation.** Pydantic at the boundary; service rules for domain
  invariants.
- **IDOR prevention.** Every request-scoped endpoint loads the resource and
  checks ownership or role before returning. Non-visible → `404`.
- **SQL injection prevention.** All queries go through SQLAlchemy with bound
  parameters. No f-strings into SQL. No string concatenation of user input
  into queries, ever.
- **Privilege escalation prevention.** Role is stored server-side and included
  in the JWT. Only admins change roles. Admins cannot demote or deactivate
  themselves (prevents lockout).
- **Secrets.** Read from environment variables at boot. `.env.example` is
  committed; `.env` is gitignored. Missing required secrets cause a fail-fast
  startup error. Secrets never appear in code, logs, tests, or commits.
- **CORS.** Configurable via `CORS_ORIGINS`. Dev default is the frontend
  origin; production is set explicitly. Never `*` with credentials.

---

## 5. Logging and Observability

- **One structured log line per request**, emitted by middleware:
  `method`, `path`, `status`, `duration_ms`, `user_id` (when authenticated).
- **Never log:** passwords, tokens, `Authorization` headers, request bodies
  containing credentials, secrets, connection strings.
- **Log domain events at meaningful points:** import summary, status
  transitions, assignment outcomes, auth failures. Include enough context to
  reconstruct what happened without exposing sensitive data.
- **Health endpoints.** `/health` is liveness only and does not touch the
  database. `/health/ready` checks the database and returns `503` if
  unreachable. Keep the two distinct — a slow database must not fail the
  liveness probe.

---

## 6. Performance

- **Do the work in the database.** Aggregation, pagination, filtering, and
  sorting happen in SQL. Python orchestrates; it does not compute over large
  result sets.
- **Indexes support queries, not tables.** Before adding an index, name the
  query it serves. Document it in `DATA_MODEL.md` §5.
- **Use keyset pagination for large tables.** Offset pagination degrades with
  depth. See `NOTES.md` (Key Decisions — Pagination).
- **Inspect queries when performance matters.** Use `EXPLAIN ANALYZE` against
  realistic data. Do not guess.
- **Keep transaction scope tight.** Long transactions hold locks and block
  other work. No HTTP calls inside transactions; no slow loops inside
  transactions.
- **Never load millions of rows into Python.** If a task needs to touch a
  large dataset, push it into SQL or a dedicated job.

---

## 7. Testing

- **Prioritize business-critical behaviour over coverage.** A green number
  means nothing if the invariants are untested.
- **Test at the highest level that gives a meaningful signal.** Most tests
  should hit the service layer or the HTTP API, not individual functions.
- **Fast and deterministic.** No sleeps, no external network, no reliance on
  wall-clock timing.
- **Real database in tests.** Run against a real Postgres (test container or
  compose service), not SQLite. Constraints, partial indexes, and `FOR UPDATE`
  behaviour must be exercised.
- **Each test owns its data.** Fresh schema per test session; truncate or
  transaction-rollback between tests.
- **Cover per feature:**
  - Happy path.
  - At least one authorization failure.
  - At least one domain-rule failure (invalid transition, insufficient
    episodes, invalid quality).
- **Cover concurrency explicitly** for the two invariant-critical paths:
  assignment exclusivity and status transition serialization.
- **Do not chase coverage percentages.** Do not test framework behaviour. Do
  not test trivial getters.

---

## 8. Git

- **Small commits.** Each commit represents one logical change.
- **Meaningful messages.** Conventional-commit style where it fits:
  `feat(auth): add JWT authentication`,
  `fix(assignments): translate integrity errors to per-episode rejections`,
  `test(requests): cover workflow transitions`.
- **Do not mix unrelated changes.** A refactor and a feature are two commits.
- **No secrets. No generated files. No IDE files.** Check `.gitignore` before
  committing.
- **Do not fake history.** Commits should reflect actual development order.

---

## 9. Anti-Patterns

Do not:

- Put business logic in route handlers.
- Put SQL in services or route handlers.
- Build SQL with f-strings or string concatenation.
- Use `SELECT *` in hot paths.
- Trigger lazy loads inside loops (N+1).
- Use `datetime.utcnow()` (deprecated and timezone-naive). Use timezone-aware
  UTC.
- Catch broad `Exception` without re-raising or logging context.
- Trust the frontend for anything security-relevant.
- Return `200` for an error, or `500` for a validation problem.
- Log secrets, tokens, or full request bodies.
- Add an index without naming the query it serves.
- Duplicate a fact across docs.
- Introduce an abstraction "for future use."

---

## 10. Engineering Judgement

> **Do not over-engineer the system.**

This is a small, single-developer system. Simple and correct beats complicated
and impressive-looking.

Do not introduce, unless there is a genuine requirement in the brief:

- Microservices
- Kafka, RabbitMQ, or any message broker
- Kubernetes or any orchestrator beyond Docker Compose
- Event sourcing
- CQRS
- Redis or any cache layer
- A background worker or scheduler
- A separate read model or read replica
- A service mesh

If you believe one of these is genuinely required, stop and write down why in
`NOTES.md` before adding it. The default answer is no.

**Priority order when making trade-offs:**

```
Correctness
    ↓
Security
    ↓
Data integrity
    ↓
Testing
    ↓
Operability
    ↓
Clarity
    ↓
Performance
    ↓
Optional sophistication
```

---

## 11. Time-boxing

Each task in the implementation plan has an estimated scope. If a task runs
past **2× its estimate**, stop and decide:

1. Reduce scope to the minimum that satisfies the acceptance criteria.
2. Document the reduction in `NOTES.md` (Simplifications).
3. Update the task and continue.

Overruns are normal. Silent overruns are not. A smaller correct system is
always better than a larger incomplete one.