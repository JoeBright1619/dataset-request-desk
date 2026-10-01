"""Opaque, bidirectional keyset-pagination cursor helpers."""

import base64
import binascii
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from app.core.errors import InvalidCursorError

CursorDirection = Literal["next", "prev"]
T = TypeVar("T")


@dataclass(frozen=True)
class Cursor:
    """A validated cursor position bound to one set of list filters."""

    sort_values: tuple[str, ...]
    direction: CursorDirection


@dataclass(frozen=True)
class CursorPage(Generic[T]):
    """A page envelope independent of the resource represented by its items."""

    items: list[T]
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool
    has_prev: bool


def filter_hash(filters: Mapping[str, Any]) -> str:
    """Return a stable digest for filters, including explicitly null values."""
    try:
        canonical = json.dumps(
            filters,
            default=_json_default,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Pagination filters must be JSON serializable") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def encode_cursor(
    sort_values: Sequence[str], direction: CursorDirection, filters: Mapping[str, Any]
) -> str:
    """Encode a sort boundary and filter fingerprint into an opaque cursor."""
    payload = {
        "sort_values": list(sort_values),
        "direction": direction,
        "filter_hash": filter_hash(filters),
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def decode_cursor(cursor: str, filters: Mapping[str, Any]) -> Cursor:
    """Decode a cursor and ensure it belongs to the requested filters."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        sort_values = payload["sort_values"]
        direction = payload["direction"]
        cursor_filter_hash = payload["filter_hash"]
    except (binascii.Error, KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError() from exc

    if (
        not isinstance(sort_values, list)
        or not sort_values
        or not all(isinstance(value, str) for value in sort_values)
        or direction not in ("next", "prev")
        or not isinstance(cursor_filter_hash, str)
        or cursor_filter_hash != filter_hash(filters)
    ):
        raise InvalidCursorError()
    return Cursor(tuple(sort_values), direction)


def build_page(
    rows: Sequence[T],
    *,
    limit: int,
    filters: Mapping[str, Any],
    requested_direction: CursorDirection | None,
    sort_values: Callable[[T], Sequence[str]],
) -> CursorPage[T]:
    """Trim an over-fetched result set and attach navigation cursors.

    ``rows`` must be in the endpoint's documented visual order. The caller
    supplies a ``limit + 1`` result set, reversing a previous-page SQL query
    before calling this helper when necessary.
    """
    has_extra = len(rows) > limit
    items = list(rows[:limit])
    if not items:
        return CursorPage([], None, None, False, False)

    if requested_direction is None:
        has_prev = False
        has_more = has_extra
    elif requested_direction == "next":
        has_prev = True
        has_more = has_extra
    else:
        has_prev = has_extra
        has_more = True
    next_cursor = (
        encode_cursor(sort_values(items[-1]), "next", filters) if has_more else None
    )
    prev_cursor = (
        encode_cursor(sort_values(items[0]), "prev", filters) if has_prev else None
    )
    return CursorPage(items, next_cursor, prev_cursor, has_more, has_prev)


def _json_default(value: Any) -> str:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    raise TypeError(f"Unsupported filter value: {type(value)!r}")
