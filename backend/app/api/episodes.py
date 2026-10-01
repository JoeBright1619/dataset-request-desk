"""Operator and administrator episode search and import endpoints."""

from datetime import datetime
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
from app.core.errors import ImportError as AppImportError
from app.db.session import get_session
from app.models.user import User
from app.schemas.episode import (
    EpisodeImportResponse,
    EpisodeListResponse,
    EpisodeQuality,
    EpisodeResponse,
)
from app.services.episode_import_service import EpisodeImportService
from app.services.episode_service import EpisodeListQuery, EpisodeService

MAX_CSV_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

router = APIRouter(prefix="/episodes", tags=["episodes"])
Session = Annotated[AsyncSession, Depends(get_session)]
OperationalUser = Annotated[User, Depends(require_roles("operator", "admin"))]


@router.post("/import", response_model=EpisodeImportResponse)
async def import_episodes(
    session: Session,
    _: OperationalUser,
    file: Annotated[UploadFile, File(...)],
) -> EpisodeImportResponse:
    """Import episodes from a CSV upload."""
    content = await file.read(MAX_CSV_FILE_SIZE + 1)
    if len(content) > MAX_CSV_FILE_SIZE:
        raise AppImportError("File exceeds maximum allowed size of 20MB")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppImportError("CSV file must be valid UTF-8 text") from exc

    try:
        summary = await EpisodeImportService(session).import_csv(StringIO(text))
    except ValueError as exc:
        raise AppImportError(str(exc)) from exc

    return EpisodeImportResponse(**summary.as_dict())


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
