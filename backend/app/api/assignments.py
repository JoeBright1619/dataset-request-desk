"""Assignment endpoints nested under /requests/{request_id}/assignments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.assignment import (
    AssignmentBatchRequest,
    AssignmentBatchResponse,
    AssignmentListResponse,
)
from app.services.assignment_service import AssignmentService

router = APIRouter(
    prefix="/requests/{request_id}/assignments",
    tags=["assignments"],
)
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=AssignmentListResponse)
async def list_assignments(
    request_id: UUID,
    session: Session,
    current_user: CurrentUser,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AssignmentListResponse:
    """List active assignments for a request."""
    return await AssignmentService(session).list_assignments(
        request_id, current_user, cursor, limit
    )


@router.post("", response_model=AssignmentBatchResponse)
async def assign_episodes(
    request_id: UUID,
    payload: AssignmentBatchRequest,
    session: Session,
    current_user: CurrentUser,
) -> AssignmentBatchResponse:
    """Batch-assign episodes to a request."""
    return await AssignmentService(session).assign_batch(
        request_id, payload.episode_ids, current_user
    )


@router.delete(
    "/{episode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def release_assignment(
    request_id: UUID,
    episode_id: str,
    session: Session,
    current_user: CurrentUser,
) -> Response:
    """Release an active assignment."""
    await AssignmentService(session).release_assignment(
        request_id, episode_id, current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
