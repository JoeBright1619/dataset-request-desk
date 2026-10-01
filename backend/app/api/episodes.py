"""Operator and administrator episode search endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
from app.db.session import get_session
from app.models.user import User
from app.schemas.episode import EpisodeListResponse, EpisodeQuality, EpisodeResponse
from app.services.episode_service import EpisodeListQuery, EpisodeService

router = APIRouter(prefix="/episodes", tags=["episodes"])
Session = Annotated[AsyncSession, Depends(get_session)]
OperationalUser = Annotated[User, Depends(require_roles("operator", "admin"))]


@router.get("", response_model=EpisodeListResponse)
async def list_episodes(
    session: Session,
    _: OperationalUser,
    task_name: str | None = None,
    quality: EpisodeQuality | None = None,
    robot_id: str | None = None,
    recorded_from: datetime | None = None,
    recorded_to: datetime | None = None,
    assigned: bool | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EpisodeListResponse:
    return await EpisodeService(session).list_episodes(
        EpisodeListQuery(
            task_name=task_name,
            quality=quality,
            robot_id=robot_id,
            recorded_from=recorded_from,
            recorded_to=recorded_to,
            assigned=assigned,
            cursor=cursor,
            limit=limit,
        )
    )


@router.get("/{episode_id}", response_model=EpisodeResponse)
async def get_episode(
    episode_id: str, session: Session, _: OperationalUser
) -> EpisodeResponse:
    return await EpisodeService(session).get_episode(episode_id)
