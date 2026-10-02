"""Persistence operations for episodes and their keyset-paginated listings."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidCursorError
from app.core.pagination import CursorPage, build_page, decode_cursor
from app.core.text import escape_like
from app.models.assignment import Assignment
from app.models.episode import Episode


@dataclass(frozen=True)
class EpisodeFilters:
    task_name: str | None = None
    quality: str | None = None
    robot_id: str | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    assigned: bool | None = None

    def as_cursor_filters(self) -> dict[str, Any]:
        return {
            "task_name": self.task_name,
            "quality": self.quality,
            "robot_id": self.robot_id,
            "recorded_from": self.recorded_from,
            "recorded_to": self.recorded_to,
            "assigned": self.assigned,
        }


class EpisodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_episode_id(self, episode_id: str) -> Episode | None:
        result = await self._session.execute(
            select(Episode).where(Episode.episode_id == episode_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, filters: EpisodeFilters, cursor: str | None, limit: int
    ) -> CursorPage[Episode]:
        cursor_filters = filters.as_cursor_filters()
        decoded_cursor = decode_cursor(cursor, cursor_filters) if cursor else None
        statement = self._filtered_statement(filters)

        if decoded_cursor is not None:
            if len(decoded_cursor.sort_values) != 2:
                raise InvalidCursorError()
            try:
                recorded_at = datetime.fromisoformat(decoded_cursor.sort_values[0])
            except ValueError as exc:
                raise InvalidCursorError() from exc
            episode_id = decoded_cursor.sort_values[1]
            boundary = or_(
                Episode.recorded_at < recorded_at,
                and_(
                    Episode.recorded_at == recorded_at,
                    Episode.episode_id < episode_id,
                ),
            )
            if decoded_cursor.direction == "next":
                statement = statement.where(boundary).order_by(
                    Episode.recorded_at.desc(), Episode.episode_id.desc()
                )
            else:
                newer_boundary = or_(
                    Episode.recorded_at > recorded_at,
                    and_(
                        Episode.recorded_at == recorded_at,
                        Episode.episode_id > episode_id,
                    ),
                )
                statement = statement.where(newer_boundary).order_by(
                    Episode.recorded_at.asc(), Episode.episode_id.asc()
                )
        else:
            statement = statement.order_by(
                Episode.recorded_at.desc(), Episode.episode_id.desc()
            )

        rows = cast(
            list[Episode],
            list((await self._session.execute(statement.limit(limit + 1))).scalars()),
        )
        if decoded_cursor is not None and decoded_cursor.direction == "prev":
            rows.reverse()
        return build_page(
            rows,
            limit=limit,
            filters=cursor_filters,
            requested_direction=(decoded_cursor.direction if decoded_cursor else None),
            sort_values=lambda episode: (
                episode.recorded_at.isoformat(),
                episode.episode_id,
            ),
        )

    async def bulk_insert_ignore_duplicates(
        self, rows: Sequence[Mapping[str, Any]]
    ) -> int:
        """Insert episodes idempotently and return the number newly created."""
        if not rows:
            return 0
        statement = (
            insert(Episode)
            .values(list(rows))
            .on_conflict_do_nothing(index_elements=[Episode.episode_id])
            .returning(Episode.id)
        )
        result = await self._session.execute(statement)
        return len(result.scalars().all())

    async def active_episode_ids(self, episode_ids: Sequence[UUID]) -> set[UUID]:
        """Return the IDs with an active assignment in one query."""
        if not episode_ids:
            return set()
        result = await self._session.execute(
            select(Assignment.episode_id).where(
                Assignment.episode_id.in_(episode_ids),
                Assignment.released_at.is_(None),
            )
        )
        return set(result.scalars().all())

    @staticmethod
    def _filtered_statement(filters: EpisodeFilters) -> Select[Episode]:
        statement = select(Episode)
        if filters.task_name is not None:
            pattern = f"{escape_like(filters.task_name)}%"
            statement = statement.where(Episode.task_name.ilike(pattern, escape="\\"))
        if filters.quality is not None:
            statement = statement.where(Episode.quality == filters.quality)
        if filters.robot_id is not None:
            pattern = f"{escape_like(filters.robot_id)}%"
            statement = statement.where(Episode.robot_id.ilike(pattern, escape="\\"))
        if filters.recorded_from is not None:
            statement = statement.where(Episode.recorded_at >= filters.recorded_from)
        if filters.recorded_to is not None:
            statement = statement.where(Episode.recorded_at < filters.recorded_to)
        if filters.assigned is not None:
            active_assignment = exists(
                select(Assignment.id).where(
                    Assignment.episode_id == Episode.id,
                    Assignment.released_at.is_(None),
                )
            )
            statement = statement.where(
                active_assignment if filters.assigned else ~active_assignment
            )
        return statement
