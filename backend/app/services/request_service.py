"""Domain service for request creation, retrieval, listing, and status transitions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ForbiddenError,
    InsufficientEpisodesError,
    InvalidTransitionError,
    NotFoundError,
)
from app.models.request import Request
from app.models.user import User
from app.repositories.request_repository import (
    RequestFilters,
    RequestRepository,
    RequestWithDetails,
)
from app.schemas.request import (
    RequestCreateRequest,
    RequestListResponse,
    RequestResponse,
    RequestStatus,
    RequestStatusUpdateRequest,
)
from app.services.authorization import ensure_resource_visible

# Status transition rules:
# Mapping: (from_status, to_status) -> allowed_roles
STATUS_TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("submitted", "in_progress"): {"operator", "admin"},
    ("in_progress", "delivered"): {"operator", "admin"},
    ("delivered", "accepted"): {"client"},
    ("delivered", "rejected"): {"client"},
    ("rejected", "in_progress"): {"operator", "admin"},
}


@dataclass(frozen=True)
class RequestListQuery:
    status: str | None = None
    client_id: UUID | None = None
    task_name: str | None = None
    cursor: str | None = None
    limit: int = 50

    def filters_for(self, current_user: User) -> RequestFilters:
        """Derive filters ensuring client users only see their own requests."""
        scoped_client_id = (
            current_user.id if current_user.role == "client" else self.client_id
        )
        return RequestFilters(
            status=self.status,
            client_id=scoped_client_id,
            task_name=self.task_name,
        )


class RequestService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._requests = RequestRepository(session)

    async def create_request(
        self, payload: RequestCreateRequest, current_user: User
    ) -> RequestResponse:
        """Create a new dataset request for a client user."""
        if current_user.role != "client":
            raise ForbiddenError("Only clients can create requests")

        request = Request(
            client_id=current_user.id,
            task_name=payload.task_name,
            episodes_requested=payload.episodes_requested,
            deadline=payload.deadline,
            notes=payload.notes,
            status="submitted",
        )
        created_request = await self._requests.create(request)
        await self._requests.append_history(
            request_id=created_request.id,
            previous_status=None,
            new_status="submitted",
            changed_by=current_user.id,
            reason=None,
        )

        return RequestResponse(
            id=created_request.id,
            client_id=created_request.client_id,
            client_name=current_user.name,
            task_name=created_request.task_name,
            episodes_requested=created_request.episodes_requested,
            episodes_assigned=0,
            deadline=created_request.deadline,
            notes=created_request.notes,
            status=cast(RequestStatus, created_request.status),
            created_at=created_request.created_at,
            updated_at=created_request.updated_at,
            delivered_at=created_request.delivered_at,
        )

    async def get_request(
        self, request_id: UUID, current_user: User
    ) -> RequestResponse:
        """Get request details by ID, enforcing client visibility scoping."""
        details = await self._requests.get_details_by_id(request_id)
        if details is None:
            raise NotFoundError()

        ensure_resource_visible(details.request.client_id, current_user)
        return self._to_response(details)

    async def list_requests(
        self, query: RequestListQuery, current_user: User
    ) -> RequestListResponse:
        """List requests with cursor pagination and client visibility scoping."""
        filters = query.filters_for(current_user)
        page = await self._requests.list(filters, query.cursor, query.limit)
        return RequestListResponse(
            items=[self._to_response(item) for item in page.items],
            next_cursor=page.next_cursor,
            prev_cursor=page.prev_cursor,
            has_more=page.has_more,
            has_prev=page.has_prev,
            limit=query.limit,
        )

    async def transition_status(
        self,
        request_id: UUID,
        payload: RequestStatusUpdateRequest,
        current_user: User,
    ) -> RequestResponse:
        """Transition the status of a request, locked with SELECT FOR UPDATE."""
        details = await self._requests.get_details_by_id(request_id, for_update=True)
        if details is None:
            raise NotFoundError()

        # Check visibility first (IDOR avoidance)
        ensure_resource_visible(details.request.client_id, current_user)

        current_status = details.request.status
        target_status = payload.status

        # If already at target status or invalid transition pair
        transition_key = (current_status, target_status)
        allowed_roles = STATUS_TRANSITIONS.get(transition_key)

        if allowed_roles is None:
            raise InvalidTransitionError(
                f"Cannot transition request from '{current_status}' "
                f"to '{target_status}'"
            )

        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{current_user.role}' is not permitted to transition "
                f"from '{current_status}' to '{target_status}'"
            )

        # Precondition check: in_progress -> delivered requires enough active episodes
        if current_status == "in_progress" and target_status == "delivered":
            if details.episodes_assigned < details.request.episodes_requested:
                raise InsufficientEpisodesError(
                    f"Assigned episodes ({details.episodes_assigned}) is less "
                    f"than requested ({details.request.episodes_requested})"
                )

        delivered_at = (
            datetime.now(UTC)
            if target_status == "delivered"
            else details.request.delivered_at
        )

        updated_request = await self._requests.update_status(
            request=details.request,
            new_status=target_status,
            delivered_at=delivered_at,
        )

        await self._requests.append_history(
            request_id=updated_request.id,
            previous_status=current_status,
            new_status=target_status,
            changed_by=current_user.id,
            reason=payload.reason,
        )

        updated_details = RequestWithDetails(
            request=updated_request,
            client_name=details.client_name,
            episodes_assigned=details.episodes_assigned,
        )
        return self._to_response(updated_details)

    @staticmethod
    def _to_response(details: RequestWithDetails) -> RequestResponse:
        return RequestResponse(
            id=details.request.id,
            client_id=details.request.client_id,
            client_name=details.client_name,
            task_name=details.request.task_name,
            episodes_requested=details.request.episodes_requested,
            episodes_assigned=details.episodes_assigned,
            deadline=details.request.deadline,
            notes=details.request.notes,
            status=cast(RequestStatus, details.request.status),
            created_at=details.request.created_at,
            updated_at=details.request.updated_at,
            delivered_at=details.request.delivered_at,
        )
