# API Reference

Canonical contract for the Dataset Request Desk HTTP API.
If code and this document disagree, the code is wrong until this file is updated.

- **Version:** v1
- **Base URL (dev):** `http://localhost:8000/api/v1`
- **Format:** JSON (UTF-8) unless stated otherwise
- **Auth:** Bearer JWT unless stated otherwise

---

## 0. Conventions

### 0.1 Authentication

Authenticated endpoints require:

```
Authorization: Bearer <access_token>
```

Access tokens are short-lived JWTs (default 30 min). Refresh tokens are opaque and rotated on use. Missing or invalid tokens return `401 AUTHENTICATION_REQUIRED`.

### 0.2 Authorization

Three roles: `client`, `operator`, `admin`. Enforced **server-side** at two checkpoints:

1. **Role check** — is this action permitted for the caller's role?
2. **Object check** — does the caller have permission for *this* resource? (e.g. does this client own this request?)

Frontend role-hiding is UX only. See Appendix B for the role matrix.

### 0.3 Pagination

List endpoints use **keyset (cursor) pagination**. Query params:

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | `50` | `1..100` |
| `cursor` | string | — | Opaque. Returned by the server on the previous page. |

Response envelope:

```json
{
  "items": [ ... ],
  "next_cursor": "eyJ...",
  "prev_cursor": "eyJ...",
  "has_more": true,
  "has_prev": false,
  "limit": 50
}
```

- `next_cursor` — next (older) page. `null` on the last page.
- `prev_cursor` — previous (newer) page. `null` on the first page.
- Both are opaque base64 tokens encoding sort position, direction, and a filter hash.
- Reusing a cursor with different filter params returns `400 INVALID_CURSOR`.
- No `total` count is returned — that would defeat keyset pagination.
- Sort order is fixed per endpoint (see each endpoint). The tiebreaker column is mandatory for stable pages.

See `NOTES.md` (Key Decisions — Pagination) for the rationale and `DATA_MODEL.md` for the supporting indexes.

### 0.4 Error envelope

All errors share one shape:

```json
{
  "error": {
    "code": "INVALID_STATUS_TRANSITION",
    "message": "Request cannot transition from delivered to submitted",
    "field": "status"
  }
}
```

`field` is optional and only present on validation errors. See Appendix C for the code list.

### 0.5 Status codes

`200` ok · `201` created · `204` deleted · `400` malformed · `401` unauthenticated · `403` forbidden · `404` not found (or not visible) · `409` conflict · `422` validation · `500` server error · `503` dependency down.

FastAPI's default `422` body is overridden so all errors match the envelope above.

### 0.6 Timestamps, IDs, enums

- Timestamps: ISO-8601 with `Z`, UTC, second precision. Stored as `TIMESTAMPTZ`.
- Internal PKs: UUIDv4, exposed as `id`.
- `episode_id`: **globally unique** external identifier from the source CSV (e.g. `episode-00123`). Used directly in URLs.
- Field names: `snake_case`. Unknown request-body fields are rejected.

### 0.7 Endpoint index

| Method | Path | Role |
|---|---|---|
| `POST` | `/auth/login` | — |
| `POST` | `/auth/refresh` | — |
| `POST` | `/auth/logout` | any |
| `GET` | `/auth/me` | any |
| `GET` | `/users` | admin |
| `POST` | `/users` | admin |
| `GET` | `/users/{user_id}` | admin |
| `PATCH` | `/users/{user_id}` | admin |
| `GET` | `/episodes` | operator, admin |
| `GET` | `/episodes/{episode_id}` | operator, admin |
| `POST` | `/episodes/import` | operator, admin |
| `GET` | `/requests` | any (scoped) |
| `POST` | `/requests` | client |
| `GET` | `/requests/{request_id}` | any (scoped) |
| `POST` | `/requests/{request_id}/status` | any (per transition) |
| `GET` | `/requests/{request_id}/assignments` | any (scoped) |
| `POST` | `/requests/{request_id}/assignments` | operator, admin |
| `DELETE` | `/requests/{request_id}/assignments/{episode_id}` | operator, admin |
| `GET` | `/analytics` | operator, admin |
| `GET` | `/health` | — |
| `GET` | `/health/ready` | — |

---

## 1. Auth

### 1.1 `POST /auth/login`

**Auth:** none.

**Request**

```json
{ "username": "alice", "password": "..." }
```

**Response `200`**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "rt_...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** `401 INVALID_CREDENTIALS` (same message for unknown user, inactive user, wrong password — no enumeration). `422 VALIDATION_ERROR`.

---

### 1.2 `POST /auth/refresh`

**Auth:** none (the refresh token is the credential).

**Request**

```json
{ "refresh_token": "rt_..." }
```

**Response `200`** — same shape as login.

**Errors:** `401 AUTHENTICATION_REQUIRED` if the token is missing, unknown, expired, or already used. Reuse revokes the entire chain for that user.

---

### 1.3 `POST /auth/logout`

**Auth:** bearer token.

**Request** (optional body)

```json
{ "refresh_token": "rt_..." }
```

If omitted, all refresh tokens for the caller are revoked.

**Response `204`**

---

### 1.4 `GET /auth/me`

**Auth:** bearer token.

**Response `200`**

```json
{
  "id": "9d8e7f6a-...",
  "username": "alice",
  "role": "operator",
  "is_active": true,
  "created_at": "2026-01-04T08:00:00Z"
}
```

---

## 2. Users

All endpoints require role `admin`.

### 2.1 `GET /users`

**Query:** `role`, `is_active`, `limit`, `cursor`.

**Sort:** `created_at DESC, id DESC`.

**Response `200`** — paginated envelope of user objects (§1.4 shape).

---

### 2.2 `POST /users`

**Request**

```json
{ "username": "bob", "password": "...", "role": "operator" }
```

**Response `201`** — created user (no password field).

**Errors:** `409 VALIDATION_ERROR` (username exists). `422 VALIDATION_ERROR`.

---

### 2.3 `GET /users/{user_id}`

**Response `200`** — user object. **Errors:** `404 NOT_FOUND`.

---

### 2.4 `PATCH /users/{user_id}`

**Request** (any subset)

```json
{ "role": "admin", "is_active": false }
```

**Response `200`** — updated user.

**Errors:** `403 FORBIDDEN` if an admin attempts to deactivate or demote themselves. `404 NOT_FOUND`. `422 VALIDATION_ERROR`.

Deactivating a user revokes their refresh tokens immediately.

---

## 3. Episodes

### 3.1 `GET /episodes`

**Auth:** operator or admin.

**Query**

| Name | Type | Notes |
|---|---|---|
| `task_name` | string | exact match |
| `quality` | enum | `good` \| `usable` \| `bad` |
| `robot_id` | string | exact match |
| `recorded_from` | datetime | inclusive |
| `recorded_to` | datetime | exclusive |
| `assigned` | bool | filter by current assignment state |
| `limit`, `cursor` | | §0.3 |

**Sort:** `recorded_at DESC, episode_id DESC`.

**Response `200`**

```json
{
  "items": [
    {
      "id": "b6a5f4e3-...",
      "episode_id": "episode-00123",
      "robot_id": "arm-01",
      "task_name": "pick_cups",
      "recorded_at": "2026-02-18T11:04:22Z",
      "duration_seconds": 42.5,
      "operator_name": "carol",
      "quality": "good",
      "is_assigned": false,
      "created_at": "2026-02-19T09:00:00Z"
    }
  ],
  "next_cursor": null,
  "prev_cursor": null,
  "has_more": false,
  "has_prev": false,
  "limit": 50
}
```

---

### 3.2 `GET /episodes/{episode_id}`

**Auth:** operator or admin.

**Path:** `episode_id` — the domain ID from the CSV, e.g. `episode-00123`.

**Response `200`** — single episode (§3.1 shape).

**Errors:** `404 NOT_FOUND`.

---

### 3.3 `POST /episodes/import`

**Auth:** operator or admin.

**Request:** `multipart/form-data` with one field:

| Field | Type | Notes |
|---|---|---|
| `file` | file | CSV, max 20 MB |

**Response `200`**

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

`errors` is capped at 100 entries. Set `errors_truncated: true` if more rows failed.

**Atomicity:** partial. Valid rows commit; invalid rows are reported. Idempotent via `UNIQUE(episode_id)`. See `NOTES.md` (Key Decisions — CSV import atomicity).

**Errors:** `400 IMPORT_ERROR` (missing/unreadable/oversized file). `422 VALIDATION_ERROR`.

The same `EpisodeImportService` backs the CLI (`python -m app.cli import-episodes <file>`). Not implemented twice.

---

## 4. Requests

### 4.1 `GET /requests`

**Auth:** any. Clients see only their own; operators and admins see all.

**Query:** `status`, `client_id` (operator/admin only; ignored for clients), `task_name`, `limit`, `cursor`.

**Sort:** `created_at DESC, id DESC`.

**Response `200`** — paginated envelope of request objects (§4.4 shape).

---

### 4.2 `POST /requests`

**Auth:** client.

**Request**

```json
{
  "task_name": "pick_cups",
  "episodes_requested": 200,
  "deadline": "2026-03-15T23:59:59Z",
  "notes": "Prefer good-quality episodes from arm-01."
}
```

**Response `201`** — created request with `status: "submitted"`.

**Errors:** `403 FORBIDDEN` (caller is not a client). `422 VALIDATION_ERROR` (including `deadline` in the past).

---

### 4.3 `GET /requests/{request_id}`

**Auth:** any.

**Visibility:** clients — only if they own it; operators and admins — always.

**Response `200`** — request object (§4.4 shape).

**Errors:** `404 NOT_FOUND` if the request does not exist **or** is not visible. `403` is deliberately not used — it would leak existence.

---

### 4.4 `POST /requests/{request_id}/status`

**Auth:** required. Permitted transition depends on caller role and request ownership. See Appendix A.

**Request**

```json
{ "status": "delivered", "reason": "Dataset assembled and QA-checked" }
```

`reason` is optional, max 500 chars, stored on the status history record.

**Response `200`** — updated request:

```json
{
  "id": "3f1c8b8e-...",
  "client_id": "9d8e7f6a-...",
  "client_name": "acme-robotics",
  "task_name": "pick_cups",
  "episodes_requested": 200,
  "episodes_assigned": 200,
  "deadline": "2026-03-15T23:59:59Z",
  "notes": "Prefer good-quality episodes from arm-01.",
  "status": "delivered",
  "created_at": "2026-03-01T10:12:00Z",
  "updated_at": "2026-03-08T14:30:11Z",
  "delivered_at": "2026-03-08T14:30:11Z"
}
```

**Errors:**

| Status | Code | When |
|---|---|---|
| `403` | `FORBIDDEN` | Role not permitted for the transition, or client does not own the request. |
| `404` | `NOT_FOUND` | Request does not exist or is not visible. |
| `409` | `INVALID_STATUS_TRANSITION` | Transition not allowed from current status. |
| `409` | `INSUFFICIENT_EPISODES` | `in_progress → delivered` with fewer assigned episodes than requested. |

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/requests/<id>/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"delivered"}'
```

Every transition writes a `request_status_history` row. Concurrency is handled by a row lock re-read inside the transaction — see `NOTES.md` (Key Decisions — Status transition concurrency).

---

## 5. Assignments

### 5.1 `GET /requests/{request_id}/assignments`

**Auth:** any. Same visibility rule as §4.3.

**Query:** `limit`, `cursor`.

**Sort:** `assigned_at DESC, episode_id DESC`.

**Response `200`**

```json
{
  "items": [
    {
      "episode_id": "episode-00123",
      "robot_id": "arm-01",
      "task_name": "pick_cups",
      "quality": "good",
      "recorded_at": "2026-02-18T11:04:22Z",
      "assigned_at": "2026-03-05T09:14:00Z",
      "assigned_by": "9d8e7f6a-..."
    }
  ],
  "next_cursor": null,
  "prev_cursor": null,
  "has_more": false,
  "has_prev": false,
  "limit": 50
}
```

---

### 5.2 `POST /requests/{request_id}/assignments`

**Auth:** operator or admin.

**Request**

```json
{ "episode_ids": ["episode-00123", "episode-00124"] }
```

1–500 items. Each is a domain `episode_id`.

**Response `200`** — batch result. Partial success is possible:

```json
{
  "request_id": "3f1c8b8e-...",
  "assigned": ["episode-00123", "episode-00124"],
  "rejected": [
    { "episode_id": "episode-00125", "reason": "already_assigned" }
  ],
  "episodes_requested": 200,
  "episodes_assigned": 187
}
```

`reason` is one of: `not_found`, `invalid_quality` (quality is `bad`), `already_assigned`.

**Errors:**

| Status | Code | When |
|---|---|---|
| `403` | `FORBIDDEN` | Caller is a client. |
| `404` | `NOT_FOUND` | Request does not exist. |
| `409` | `INVALID_STATUS_TRANSITION` | Request is not in `submitted` or `in_progress`. |
| `422` | `VALIDATION_ERROR` | Empty list, more than 500 items, malformed IDs. |

Concurrency is guaranteed by a partial unique index — see `NOTES.md` (Key Decisions — Assignment concurrency).

---

### 5.3 `DELETE /requests/{request_id}/assignments/{episode_id}`

**Auth:** operator or admin.

**Response `204`**

**Errors:** `404 NOT_FOUND`. `409 INVALID_STATUS_TRANSITION` if the request is not `submitted` or `in_progress`.

Release is a soft release (`released_at = now()`), so history is preserved and the episode becomes assignable again.

---

## 6. Analytics

### 6.1 `GET /analytics`

**Auth:** operator or admin.

**Query:** `from` (inclusive, required), `to` (exclusive, required), `robot_id` (optional).

**Response `200`**

```json
{
  "range": { "from": "2026-02-01T00:00:00Z", "to": "2026-03-01T00:00:00Z" },
  "episodes_by_day_robot": [
    { "date": "2026-02-01", "robot_id": "arm-01", "count": 412 }
  ],
  "requests_by_status": [
    { "status": "in_progress", "count": 34 }
  ],
  "median_submitted_to_delivered_hours": 41.5,
  "top_tasks_by_good_episodes": [
    { "task_name": "pick_cups", "good_episodes": 1893 }
  ]
}
```

All aggregation is executed in the database. See `NOTES.md` for behaviour at ~5M episodes.

**Errors:** `403 FORBIDDEN`. `422 VALIDATION_ERROR` (missing `from`/`to`, or `from >= to`).

---

## 7. Operational

### 7.1 `GET /health`

**Auth:** none. Liveness only — does not touch the database.

**Response `200`**

```json
{ "status": "ok" }
```

---

### 7.2 `GET /health/ready`

**Auth:** none. Readiness — checks database connectivity with a short timeout.

**Response `200`**

```json
{ "status": "ready", "checks": { "database": "ok" } }
```

**Response `503`**

```json
{ "status": "not_ready", "checks": { "database": "unreachable" } }
```

---

## Appendix A — Status Transition Matrix

Canonical source for `POST /requests/{request_id}/status`.

| From | To | Role | Extra condition |
|---|---|---|---|
| `submitted` | `in_progress` | operator, admin | — |
| `in_progress` | `delivered` | operator, admin | `episodes_assigned >= episodes_requested` |
| `delivered` | `accepted` | client (owner) | — |
| `delivered` | `rejected` | client (owner) | — |
| `rejected` | `in_progress` | operator, admin | — |

Anything else → `409 INVALID_STATUS_TRANSITION`. `accepted` is terminal. Assignments are not cleared on rejection.

---

## Appendix B — Role Permission Matrix

| Capability | client | operator | admin |
|---|---|---|---|
| Login / refresh / logout / me | ✅ | ✅ | ✅ |
| Create request | ✅ | ❌ | ❌ |
| View own requests | ✅ | — | — |
| View all requests | ❌ | ✅ | ✅ |
| Accept / reject own delivered request | ✅ | — | — |
| Move request through operational states | ❌ | ✅ | ✅ |
| View / import / filter episodes | ❌ | ✅ | ✅ |
| Assign / release episodes | ❌ | ✅ | ✅ |
| View analytics | ❌ | ✅ | ✅ |
| Manage users | ❌ | ❌ | ✅ |

"Own" is enforced at the object level, not just at the role level.

---

## Appendix C — Error Codes

| Code | HTTP | Meaning |
|---|---|---|
| `AUTHENTICATION_REQUIRED` | 401 | Missing, invalid, or expired token. |
| `INVALID_CREDENTIALS` | 401 | Bad username or password at login. |
| `FORBIDDEN` | 403 | Role or object-level permission denied. |
| `NOT_FOUND` | 404 | Resource does not exist, or is not visible to the caller. |
| `VALIDATION_ERROR` | 422 | Request body or parameters failed validation. |
| `INVALID_CURSOR` | 400 | Cursor is malformed or its filter hash does not match the request. |
| `INVALID_STATUS_TRANSITION` | 409 | Request state machine does not permit this operation. |
| `INSUFFICIENT_EPISODES` | 409 | Delivering with fewer assigned episodes than requested. |
| `EPISODE_ALREADY_ASSIGNED` | 409 | Returned inside the batch `rejected` array (HTTP stays `200` for partial success). |
| `INVALID_EPISODE_QUALITY` | 422 | Returned inside the batch `rejected` array for `bad` episodes. |
| `IMPORT_ERROR` | 400 | CSV file missing, unreadable, or too large. |
| `INTERNAL_ERROR` | 500 | Unexpected server error. Internals never exposed. |

---

## Appendix D — Enums

| Enum | Values |
|---|---|
| User role | `client`, `operator`, `admin` |
| Episode quality | `good`, `usable`, `bad` (only `good` and `usable` are assignable) |
| Request status | `submitted`, `in_progress`, `delivered`, `accepted`, `rejected` (`accepted` is terminal) |