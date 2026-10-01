"""Persistence operations for assignments and their keyset-paginated listings."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidCursorError
from app.core.pagination import CursorPage, build_page, decode_cursor
from app.models.assignment import Assignment
from app.models.episode import Episode


@dataclass(frozen=True)
class AssignmentWithEpisode:
    assignment: Assignment
    episode_domain_id: str
    robot_id: str
    task_name: str
    quality: str
    recorded_at: datetime
    assigned_by: UUID
    assigned_at: datetime


RejectionReason = Literal["not_found", "invalid_quality", "already_assigned"]


@dataclass(frozen=True)
class RejectedAssignment:
    episode_id: str
    reason: RejectionReason


@dataclass(frozen=True)
class BatchAssignmentResult:
    assigned: list[str]
    rejected: list[RejectedAssignment]


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active_by_request_id(
        self, request_id: UUID, cursor: str | None, limit: int
    ) -> CursorPage[AssignmentWithEpisode]:
        """List active assignments for a request with cursor pagination.

        Sort: assigned_at DESC, episode_id DESC (using domain episode_id).
        """
        cursor_filters = {"request_id": str(request_id)}
        decoded_cursor = decode_cursor(cursor, cursor_filters) if cursor else None

        statement = (
            select(
                Assignment,
                Episode.episode_id.label("episode_domain_id"),
                Episode.robot_id,
                Episode.task_name,
                Episode.quality,
                Episode.recorded_at,
            )
            .join(Episode, Assignment.episode_id == Episode.id)
            .where(
                Assignment.request_id == request_id,
                Assignment.released_at.is_(None),
            )
        )

        if decoded_cursor is not None:
            if len(decoded_cursor.sort_values) != 2:
                raise InvalidCursorError()
            try:
                assigned_at = datetime.fromisoformat(decoded_cursor.sort_values[0])
            except (ValueError, TypeError) as exc:
                raise InvalidCursorError() from exc
            episode_domain_id = decoded_cursor.sort_values[1]

            boundary = or_(
                Assignment.assigned_at < assigned_at,
                and_(
                    Assignment.assigned_at == assigned_at,
                    Episode.episode_id < episode_domain_id,
                ),
            )
            if decoded_cursor.direction == "next":
                statement = statement.where(boundary).order_by(
                    Assignment.assigned_at.desc(), Episode.episode_id.desc()
                )
            else:
                newer_boundary = or_(
                    Assignment.assigned_at > assigned_at,
                    and_(
                        Assignment.assigned_at == assigned_at,
                        Episode.episode_id > episode_domain_id,
                    ),
                )
                statement = statement.where(newer_boundary).order_by(
                    Assignment.assigned_at.asc(), Episode.episode_id.asc()
                )
        else:
            statement = statement.order_by(
                Assignment.assigned_at.desc(), Episode.episode_id.desc()
            )

        result = await self._session.execute(statement.limit(limit + 1))
        rows = [
            AssignmentWithEpisode(
                assignment=row[0],
                episode_domain_id=row[1],
                robot_id=row[2],
                task_name=row[3],
                quality=row[4],
                recorded_at=row[5],
                assigned_by=row[0].assigned_by,
                assigned_at=row[0].assigned_at,
            )
            for row in result.all()
        ]

        if decoded_cursor is not None and decoded_cursor.direction == "prev":
            rows.reverse()

        return build_page(
            rows,
            limit=limit,
            filters=cursor_filters,
            requested_direction=(decoded_cursor.direction if decoded_cursor else None),
            sort_values=lambda item: (
                item.assigned_at.isoformat(),
                item.episode_domain_id,
            ),
        )

    async def assign_batch(
        self, request_id: UUID, episode_ids: list[str], user_id: UUID
    ) -> BatchAssignmentResult:
        """Attempt to assign episodes to a request in order.

        Validation rules:
        - `not_found`: episode doesn't exist.
        - `invalid_quality`: episode quality is 'bad'.
        - `already_assigned`: active assignment exists for this episode.

        Catches IntegrityError per row using savepoint (`session.begin_nested()`)
        to guarantee partial-unique-safe atomic attempts.
        """
        assigned: list[str] = []
        rejected: list[RejectedAssignment] = []

        if not episode_ids:
            return BatchAssignmentResult(assigned=assigned, rejected=rejected)

        # Batch lookup domain episodes
        episodes_result = await self._session.execute(
            select(Episode).where(Episode.episode_id.in_(episode_ids))
        )
        episodes_by_domain_id = {
            ep.episode_id: ep for ep in episodes_result.scalars().all()
        }

        # Track already processed in this batch to prevent duplicate attempt collision
        assigned_in_this_batch: set[UUID] = set()

        for ep_domain_id in episode_ids:
            episode = episodes_by_domain_id.get(ep_domain_id)
            if episode is None:
                rejected.append(
                    RejectedAssignment(episode_id=ep_domain_id, reason="not_found")
                )
                continue

            if episode.quality == "bad":
                rejected.append(
                    RejectedAssignment(
                        episode_id=ep_domain_id, reason="invalid_quality"
                    )
                )
                continue

            if episode.id in assigned_in_this_batch:
                rejected.append(
                    RejectedAssignment(
                        episode_id=ep_domain_id, reason="already_assigned"
                    )
                )
                continue

            # Attempt insert using a savepoint to catch partial unique violation
            try:
                async with self._session.begin_nested():
                    assignment = Assignment(
                        request_id=request_id,
                        episode_id=episode.id,
                        assigned_by=user_id,
                    )
                    self._session.add(assignment)
                    await self._session.flush()
                assigned.append(ep_domain_id)
                assigned_in_this_batch.add(episode.id)
            except IntegrityError:
                rejected.append(
                    RejectedAssignment(
                        episode_id=ep_domain_id, reason="already_assigned"
                    )
                )

        return BatchAssignmentResult(assigned=assigned, rejected=rejected)

    async def release(
        self,
        request_id: UUID,
        episode_domain_id: str,
        release_reason: str | None = None,
    ) -> bool:
        """Release active assignment for the given request and episode.

        Returns True if an active assignment was released, False otherwise.
        """
        # Look up episode internal UUID
        episode_result = await self._session.execute(
            select(Episode.id).where(Episode.episode_id == episode_domain_id)
        )
        episode_pk = episode_result.scalar_one_or_none()
        if episode_pk is None:
            return False

        statement = select(Assignment).where(
            Assignment.request_id == request_id,
            Assignment.episode_id == episode_pk,
            Assignment.released_at.is_(None),
        )
        result = await self._session.execute(statement)
        assignment = result.scalar_one_or_none()
        if assignment is None:
            return False

        assignment.released_at = datetime.now(UTC)
        assignment.release_reason = release_reason
        await self._session.flush()
        return True
