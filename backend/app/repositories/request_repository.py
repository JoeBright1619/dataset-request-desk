"""Persistence operations for requests and their status history."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Integer, Select, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidCursorError
from app.core.pagination import CursorPage, build_page, decode_cursor
from app.models.assignment import Assignment
from app.models.request import Request
from app.models.request_status_history import RequestStatusHistory
from app.models.user import User


@dataclass(frozen=True)
class RequestFilters:
    status: str | None = None
    client_id: UUID | None = None
    task_name: str | None = None

    def as_cursor_filters(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "client_id": str(self.client_id) if self.client_id else None,
            "task_name": self.task_name,
        }


@dataclass(frozen=True)
class RequestWithDetails:
    request: Request
    client_name: str
    episodes_assigned: int


class RequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, request_id: UUID, for_update: bool = False
    ) -> Request | None:
        statement = select(Request).where(Request.id == request_id)
        if for_update:
            statement = statement.with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_details_by_id(
        self, request_id: UUID, for_update: bool = False
    ) -> RequestWithDetails | None:
        active_assignments_subq = (
            select(
                Assignment.request_id,
                func.count(Assignment.id).label("episodes_assigned"),
            )
            .where(Assignment.released_at.is_(None))
            .group_by(Assignment.request_id)
            .subquery()
        )

        statement = (
            select(
                Request,
                User.name.label("client_name"),
                cast(
                    func.coalesce(active_assignments_subq.c.episodes_assigned, 0),
                    Integer,
                ).label("episodes_assigned"),
            )
            .join(User, Request.client_id == User.id)
            .outerjoin(
                active_assignments_subq,
                Request.id == active_assignments_subq.c.request_id,
            )
            .where(Request.id == request_id)
        )
        if for_update:
            statement = statement.with_for_update(of=Request)

        result = await self._session.execute(statement)
        row = result.tuples().one_or_none()
        if row is None:
            return None
        return RequestWithDetails(
            request=row[0],
            client_name=row[1],
            episodes_assigned=row[2],
        )

    async def list(
        self, filters: RequestFilters, cursor: str | None, limit: int
    ) -> CursorPage[RequestWithDetails]:
        cursor_filters = filters.as_cursor_filters()
        decoded_cursor = decode_cursor(cursor, cursor_filters) if cursor else None
        statement = self._filtered_statement(filters)

        if decoded_cursor is not None:
            if len(decoded_cursor.sort_values) != 2:
                raise InvalidCursorError()
            try:
                created_at = datetime.fromisoformat(decoded_cursor.sort_values[0])
                item_id = UUID(decoded_cursor.sort_values[1])
            except (ValueError, TypeError) as exc:
                raise InvalidCursorError() from exc

            boundary = or_(
                Request.created_at < created_at,
                and_(
                    Request.created_at == created_at,
                    Request.id < item_id,
                ),
            )
            if decoded_cursor.direction == "next":
                statement = statement.where(boundary).order_by(
                    Request.created_at.desc(), Request.id.desc()
                )
            else:
                newer_boundary = or_(
                    Request.created_at > created_at,
                    and_(
                        Request.created_at == created_at,
                        Request.id > item_id,
                    ),
                )
                statement = statement.where(newer_boundary).order_by(
                    Request.created_at.asc(), Request.id.asc()
                )
        else:
            statement = statement.order_by(Request.created_at.desc(), Request.id.desc())

        result = await self._session.execute(statement.limit(limit + 1))
        rows = [
            RequestWithDetails(
                request=row[0],
                client_name=row[1],
                episodes_assigned=row[2],
            )
            for row in result.tuples().all()
        ]

        if decoded_cursor is not None and decoded_cursor.direction == "prev":
            rows.reverse()

        return build_page(
            rows,
            limit=limit,
            filters=cursor_filters,
            requested_direction=(decoded_cursor.direction if decoded_cursor else None),
            sort_values=lambda item: (
                item.request.created_at.isoformat(),
                str(item.request.id),
            ),
        )

    async def create(self, request: Request) -> Request:
        self._session.add(request)
        await self._session.flush()
        return request

    async def update_status(
        self,
        request: Request,
        new_status: str,
        delivered_at: datetime | None = None,
    ) -> Request:
        request.status = new_status
        if delivered_at is not None:
            request.delivered_at = delivered_at
        await self._session.flush()
        return request

    async def append_history(
        self,
        request_id: UUID,
        previous_status: str | None,
        new_status: str,
        changed_by: UUID,
        reason: str | None = None,
    ) -> RequestStatusHistory:
        history = RequestStatusHistory(
            request_id=request_id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
        self._session.add(history)
        await self._session.flush()
        return history

    async def list_history(self, request_id: UUID) -> Sequence[RequestStatusHistory]:
        statement = (
            select(RequestStatusHistory)
            .where(RequestStatusHistory.request_id == request_id)
            .order_by(RequestStatusHistory.changed_at.desc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def count_active_assignments(self, request_id: UUID) -> int:
        statement = select(func.count(Assignment.id)).where(
            Assignment.request_id == request_id,
            Assignment.released_at.is_(None),
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    @staticmethod
    def _filtered_statement(
        filters: RequestFilters,
    ) -> Select[Request, str, int]:
        active_assignments_subq = (
            select(
                Assignment.request_id,
                func.count(Assignment.id).label("episodes_assigned"),
            )
            .where(Assignment.released_at.is_(None))
            .group_by(Assignment.request_id)
            .subquery()
        )

        statement = (
            select(
                Request,
                User.name.label("client_name"),
                cast(
                    func.coalesce(active_assignments_subq.c.episodes_assigned, 0),
                    Integer,
                ).label("episodes_assigned"),
            )
            .join(User, Request.client_id == User.id)
            .outerjoin(
                active_assignments_subq,
                Request.id == active_assignments_subq.c.request_id,
            )
        )

        if filters.status is not None:
            statement = statement.where(Request.status == filters.status)
        if filters.client_id is not None:
            statement = statement.where(Request.client_id == filters.client_id)
        if filters.task_name is not None:
            statement = statement.where(Request.task_name == filters.task_name)

        return statement
