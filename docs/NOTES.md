# Notes

Engineering notes on the Dataset Request Desk. Companion to `README.md` (how to
run) and `GUIDE.md` (rules). Design details live in `docs/`.

---

## Design

Six tables: `users`, `episodes`, `requests`, `assignments`,
`request_status_history`, `refresh_tokens`.

```
users ──< requests ──< assignments >── episodes
  │          │
  │          └──< request_status_history
  └──< refresh_tokens
```

**Where state lives.** Request status is on `requests.status`; every transition
appends to `request_status_history`. Assignment state is derived from
`assignments` where `released_at IS NULL` — never stored on `episodes`.
`episodes_assigned` is not a column; it is computed at read time so it cannot
drift.

**Logic lives in services, not route handlers.** Invariants that must survive
concurrency are enforced by the database: `UNIQUE(episode_id)` on episodes and
a partial unique index on active assignments. Everything else (roles,
ownership, transitions, delivery readiness) lives in the service layer.

**Hardest decisions.**

1. **Assignment concurrency.** Two operators assigning the same episode must
   not both succeed. Chose a partial unique index
   `UNIQUE(episode_id) WHERE released_at IS NULL` — the DB guarantees
   exclusivity, and release-then-reassign works naturally. Application checks
   are only for a friendlier error message.
2. **Pagination.** Brief explicitly frames 5M episodes. Chose keyset (cursor)
   with bidirectional `next_cursor` / `prev_cursor`. Offset degrades with
   depth; the operator UI browses sequentially, which is what keyset is for.
   Cursor carries a filter hash so changing filters mid-scroll returns
   `400 INVALID_CURSOR` instead of a nonsense page.
3. **Status transition concurrency.** The check depends on current status, so
   read-then-write must serialize. Chose `SELECT ... FOR UPDATE` on the request
   row inside the transition transaction. Optimistic locking would add a
   version column and retry loop for no practical benefit at this volume.

---

## Simplifications

**Left out on purpose:**

- Password reset and change. Users are created by an admin; password is set
  then.
- Rate limiting on `/auth/login` and `/auth/refresh`. Would sit behind a
  gateway in production.
- Background jobs / schedulers. CSV import is synchronous and bounded.
- Email notifications, i18n, audit UI.
- Soft-delete for episodes and requests. Episodes are append-only; requests
  are never removed.

**With two more days I would:**

1. Write the regression test for the cursor filter-hash bug (see below), and
   close the other testing gaps noted throughout these notes.
2. Add rate limiting on `/auth/login` and `/auth/refresh`.
3. Add password reset and password change flows.
4. Move analytics to a materialised view and, if time allows, add monthly
   partitioning on `episodes(recorded_at)`.
5. Add an admin audit view backed by `request_status_history` and
   `assignments`.
6. Complete the stretch feature (Phase 10 of `PLAN.md`), evaluating the three
   options against the remaining scope and implementing the strongest one.
7. Improve the frontend: replace the current minimal UI with a proper design
   system, add keyboard navigation and basic accessibility, fill in the
   missing views (audit, user management), and polish the operator workflow
   so it feels like a tool rather than a proof of concept.

Beyond adding features, I would use the extra time to go back through every
task in `PLAN.md` with the same attention I gave to the ones that went well —
verifying that nothing was rushed, that tests cover the behaviour actually
shipped, that edge cases in the state machine and assignment flow have been
exercised, and that the docs still match the code. A few of the tasks were
finished under deadline pressure, and with two more days I would treat the
whole implementation as if it were being reviewed line by line, rather than
moving straight on to new work.

---

## Something That Went Wrong

Cursor pagination initially encoded only sort position and direction, not the
active filters. The bug:

1. Client loads page 1 with `?task_name=speech`.
2. Client changes to `?task_name=vision` and sends the same cursor.
3. Server combined the *new* filter with the *old* cursor anchor, returning a
   slice from the middle of the vision-filtered set — `200 OK`, plausible
   results, wrong data.

**Diagnosis.** Inconsistent totals appeared only when switching filters mid-
pagination. Single-filter tests passed; the bug needed a filter change between
pages. Adding logging of the sort anchor confirmed the cursor was being reused
across different result sets.

**Fix.** Cursor now carries `sha256(canonical filter set)`. On every paginated
request, the server recomputes the hash and rejects mismatches with
`400 INVALID_CURSOR`. A cursor can no longer be reused across filter changes.

**Not done:** no dedicated regression test for this sequence. It is on the
two-more-days list.

---

## Security

**Passwords.** bcrypt with per-password salt. Never logged or echoed.
Login failures return `401 INVALID_CREDENTIALS` with the same message for
unknown user, inactive user, and wrong password — no enumeration.

**Tokens.** JWT access tokens (30 min, `Authorization: Bearer`). Refresh
tokens are opaque (`rt_<urlsafe(32)>`), SHA-256 hashed in the DB, rotated on
use, grouped by `family_id`. Reuse of a used token revokes the whole family —
and that revocation is committed explicitly before the error propagates, so it
survives the request-session rollback.

**Input validation.** Pydantic at the HTTP boundary (shape, types, ranges,
unknown fields rejected). Service rules for domain invariants. SQLAlchemy with
bound parameters — no string concatenation into SQL. All errors use one
envelope; stack traces and SQL are never returned.

**Two vulnerabilities I'd worry about most:**

1. **IDOR.** Every request-scoped endpoint loads the resource and checks
   ownership or role in the service. Non-visible resources return `404`, not
   `403`, so existence is not leaked.
2. **Token theft via XSS.** Tokens are stored client-side and sent as Bearer
   headers. An XSS bug would let an attacker steal the access token (30 min)
   and the refresh token (persistent). Family revocation limits the window but
   does not eliminate it. Mitigations: strict CSP, dependency audits, and
   ideally moving the refresh token to an HttpOnly cookie in production.

Not implemented but acknowledged: rate limiting, account lockout, password
strength rules.

---

## Scale

**At 10× users (thousands concurrent):** the DB connection pool is the first
thing to bite — tune pool size, add PgBouncer. Then `/auth/login` under
credential stuffing (no limiter). Then write contention on `requests` as
status transitions take a row lock.

**At 100× episodes (~50M rows):** browse stays fast — keyset pagination does
not degrade with depth, and the composite indexes on `episodes` carry the
load. The first pain point is the analytics aggregation, particularly the
median (`percentile_cont` sorts the range). Fix order: materialised view
refreshed hourly → monthly partitioning on `episodes(recorded_at)` → t-digest
approximation for the median. Storage stays modest (~15 GB). Index count on
`episodes` is deliberately limited — every extra index slows import.

**First changes I'd make:** materialised view for analytics, then monthly
partitioning, then PgBouncer, then a read replica if browse and analytics
contend.

---

## AI Tooling

Used LLM chat assistants (mainly Claude) as **design reviewers and drafting
aids** — not agentic coding tools. The free tiers I had access to were not
reliable enough for repo-aware work, and paid tiers were out of scope for a
technical test. Every file was written by hand with chat-based assistance
rather than generated and reviewed, which is why the build took significantly
longer than it would have with an agent.

**For:** doc drafting (`docs/API.md`, `docs/DATA_MODEL.md`,
`docs/ARCHITECTURE.md`, this file), design review (the assistant caught the
check-then-act assignment race at design time and pushed back on offset
pagination given the 5M framing), FastAPI / Pydantic / Alembic boilerplate,
and debugging hints on the cursor filter-hash bug.

**Not for:** business rule implementation without line-by-line review, test
assertions (written by hand so expectations reflect intent, not behaviour),
authentication and authorization code (read in full before committing).

Every AI-suggested change was reviewed against `GUIDE.md` before being
accepted. One suggestion was rejected: a standalone `DECISIONS.md` — dropped
in favour of folding decisions into this file, since the brief already requires
`NOTES.md` to cover design decisions.