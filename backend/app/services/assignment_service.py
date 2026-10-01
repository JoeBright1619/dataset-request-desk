"""Domain service for assignment listing, batch creation, and release."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
)
from app.models.user import User
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.request_repository import RequestRepository
from app.schemas.assignment import (
    AssignmentBatchResponse,
    AssignmentItemResponse,
    AssignmentListResponse,
    RejectedAssignmentResponse,
)
from app.services.authorization import ensure_resource_visible

_ASSIGNABLE_STATUSES = frozenset({"submitted", "in_progress"})


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._assignments = AssignmentRepository(session)
        self._requests = RequestRepository(session)

    async def list_assignments(
        self,
        request_id: UUID,
        current_user: User,
        cursor: str | None,
        limit: int,
    ) -> AssignmentListResponse:
        """List active assignments visible to the caller."""
        details = await self._requests.get_details_by_id(request_id)
        if details is None:
            raise NotFoundError()
        ensure_resource_visible(details.request.client_id, current_user)

        page = await self._assignments.list_active_by_request_id(
            request_id, cursor, limit
        )
        return AssignmentListResponse(
            items=[
                AssignmentItemResponse(
                    episode_id=item.episode_domain_id,
                    robot_id=item.robot_id,
                    task_name=item.task_name,
                    quality=item.quality,
                    recorded_at=item.recorded_at,
                    assigned_at=item.assigned_at,
                    assigned_by=item.assigned_by,
                )
                for item in page.items
            ],
            next_cursor=page.next_cursor,
            prev_cursor=page.prev_cursor,
            has_more=page.has_more,
            has_prev=page.has_prev,
            limit=limit,
        )

    async def assign_batch(
        self,
        request_id: UUID,
        episode_ids: list[str],
        current_user: User,
    ) -> AssignmentBatchResponse:
        """Batch-assign episodes to a request."""
        if current_user.role not in ("operator", "admin"):
            raise ForbiddenError()

        details = await self._requests.get_details_by_id(request_id)
        if details is None:
            raise NotFoundError()

        if details.request.status not in _ASSIGNABLE_STATUSES:
            raise InvalidTransitionError(
                "Assignments can only be added when the request "
                f"is in {', '.join(sorted(_ASSIGNABLE_STATUSES))}; "
                f"current status is '{details.request.status}'"
            )

        result = await self._assignments.assign_batch(
            request_id, episode_ids, current_user.id
        )

        new_count = await self._requests.count_active_assignments(request_id)

        return AssignmentBatchResponse(
            request_id=request_id,
            assigned=result.assigned,
            rejected=[
                RejectedAssignmentResponse(
                    episode_id=r.episode_id,
                    reason=r.reason,
                )
                for r in result.rejected
            ],
            episodes_requested=details.request.episodes_requested,
            episodes_assigned=new_count,
        )

    async def release_assignment(
        self,
        request_id: UUID,
        episode_id: str,
        current_user: User,
    ) -> None:
        """Release an active assignment."""
        if current_user.role not in ("operator", "admin"):
            raise ForbiddenError()

        details = await self._requests.get_details_by_id(request_id)
        if details is None:
            raise NotFoundError()

        if details.request.status not in _ASSIGNABLE_STATUSES:
            raise InvalidTransitionError(
                "Assignments can only be released when the request "
                f"is in {', '.join(sorted(_ASSIGNABLE_STATUSES))}; "
                f"current status is '{details.request.status}'"
            )

        released = await self._assignments.release(request_id, episode_id)
        if not released:
            raise NotFoundError("Active assignment not found for this episode")
