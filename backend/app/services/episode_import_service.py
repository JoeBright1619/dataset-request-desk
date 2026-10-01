"""Transport-independent, partially successful CSV episode importer."""

import csv
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, TextIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.episode_repository import EpisodeRepository

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = frozenset(
    {
        "episode_id",
        "robot_id",
        "task_name",
        "recorded_at",
        "duration_seconds",
        "quality",
    }
)
MAX_ERRORS = 100
VALID_QUALITIES = frozenset({"good", "usable", "bad"})


@dataclass(frozen=True)
class ImportRowError:
    row: int
    reason: str
    raw: dict[str, str | None]


@dataclass(frozen=True)
class EpisodeImportSummary:
    imported: int
    skipped_duplicates: int
    invalid: int
    errors: list[ImportRowError]
    errors_truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "imported": self.imported,
            "skipped_duplicates": self.skipped_duplicates,
            "invalid": self.invalid,
            "errors": [asdict(error) for error in self.errors],
            "errors_truncated": self.errors_truncated,
        }


class EpisodeImportService:
    """Validate CSV rows and insert valid episode records idempotently."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._episodes = EpisodeRepository(session)

    async def import_csv(self, stream: TextIO) -> EpisodeImportSummary:
        """Import an episode CSV stream with the header defined in ``API.md``."""
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("CSV file is missing a header row")
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            names = ", ".join(sorted(missing_columns))
            raise ValueError(f"CSV file is missing required columns: {names}")
        return await self.import_rows(reader, row_numbers=lambda: reader.line_num)

    async def import_rows(
        self,
        rows: Iterable[Mapping[str, str | None]],
        *,
        row_numbers: Callable[[], int] | None = None,
    ) -> EpisodeImportSummary:
        """Import parsed CSV rows; useful to both HTTP and CLI adapters."""
        valid_rows: list[dict[str, Any]] = []
        errors: list[ImportRowError] = []
        invalid = 0

        for index, row in enumerate(rows, start=2):
            raw = dict(row)
            row_number = row_numbers() if row_numbers is not None else index
            try:
                valid_rows.append(_parse_row(raw))
            except ValueError as exc:
                invalid += 1
                if len(errors) < MAX_ERRORS:
                    errors.append(ImportRowError(row_number, str(exc), raw))

        inserted = await self._episodes.bulk_insert_ignore_duplicates(valid_rows)
        await self._session.commit()
        summary = EpisodeImportSummary(
            imported=inserted,
            skipped_duplicates=len(valid_rows) - inserted,
            invalid=invalid,
            errors=errors,
            errors_truncated=invalid > MAX_ERRORS,
        )
        logger.info(
            "episode_import_complete imported=%s skipped_duplicates=%s invalid=%s",
            summary.imported,
            summary.skipped_duplicates,
            summary.invalid,
        )
        return summary


def _parse_row(row: Mapping[str, str | None]) -> dict[str, Any]:
    episode_id = _required(row, "episode_id", max_length=64)
    robot_id = _required(row, "robot_id", max_length=64)
    task_name = _required(row, "task_name", max_length=128)
    recorded_at = _parse_recorded_at(_required(row, "recorded_at"))
    duration_seconds = _parse_duration(_required(row, "duration_seconds"))
    quality = _required(row, "quality", max_length=16)
    if quality not in VALID_QUALITIES:
        raise ValueError("quality must be one of: good, usable, bad")

    operator_name = row.get("operator_name")
    if operator_name is not None:
        operator_name = operator_name.strip() or None
        if operator_name is not None and len(operator_name) > 128:
            raise ValueError("operator_name must be at most 128 characters")

    return {
        "episode_id": episode_id,
        "robot_id": robot_id,
        "task_name": task_name,
        "recorded_at": recorded_at,
        "duration_seconds": duration_seconds,
        "operator_name": operator_name,
        "quality": quality,
    }


def _required(
    row: Mapping[str, str | None], field: str, max_length: int | None = None
) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise ValueError(f"missing {field}")
    value = value.strip()
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    return value


def _parse_recorded_at(value: str) -> datetime:
    try:
        recorded_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("recorded_at must be an ISO-8601 timestamp") from exc
    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at must include a timezone")
    recorded_at = recorded_at.astimezone(UTC)
    if recorded_at > datetime.now(UTC):
        raise ValueError("recorded_at cannot be in the future")
    return recorded_at


def _parse_duration(value: str) -> Decimal:
    try:
        duration = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("duration_seconds must be a number") from exc
    if not duration.is_finite() or duration <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    exponent = duration.as_tuple().exponent
    decimal_places = -exponent if isinstance(exponent, int) else 0
    if decimal_places > 2 or duration >= Decimal("100000000"):
        raise ValueError("duration_seconds must fit NUMERIC(10,2)")
    return duration
