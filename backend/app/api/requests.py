"""Endpoints for dataset request creation, listing, and inspection."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.request import (
    RequestCreateRequest,
    RequestListResponse,
    RequestResponse,
    RequestStatus,
)
from app.services.request_service import RequestListQuery, RequestService

router = APIRouter(prefix="/requests", tags=["requests"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: RequestCreateRequest,
    session: Session,
    current_user: CurrentUser,
) -> RequestResponse:
    """Create a new dataset request (clients only)."""
    return await RequestService(session).create_request(payload, current_user)


@router.get("", response_model=RequestListResponse)
async def list_requests(
    session: Session,
    current_user: CurrentUser,
    status: RequestStatus | None = None,
    client_id: UUID | None = None,
    task_name: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RequestListResponse:
    """List requests visible to current user with cursor pagination."""
    return await RequestService(session).list_requests(
        RequestListQuery(
            status=status,
            client_id=client_id,
            task_name=task_name,
            cursor=cursor,
            limit=limit,
        ),
        current_user=current_user,
    )


@router.get("/{request_id}", response_model=RequestResponse)
async def get_request(
    request_id: UUID,
    session: Session,
    current_user: CurrentUser,
) -> RequestResponse:
    """Get single request by ID if visible to current user."""
    return await RequestService(session).get_request(request_id, current_user)
