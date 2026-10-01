"""Operator and administrator analytics endpoint."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
from app.db.session import get_session
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsRange,
    AnalyticsResponse,
    EpisodesByDayRobotResponse,
    RequestsByStatusResponse,
    TopTaskByGoodEpisodesResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

Session = Annotated[AsyncSession, Depends(get_session)]
OperationalUser = Annotated[User, Depends(require_roles("operator", "admin"))]


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    session: Session,
    _: OperationalUser,
    from_: Annotated[datetime, Query(alias="from")],
    to: datetime,
    robot_id: str | None = None,
) -> AnalyticsResponse:
    result = await AnalyticsService(session).get_analytics(
        range_from=from_,
        range_to=to,
        robot_id=robot_id,
    )

    return AnalyticsResponse(
        range=AnalyticsRange(
            **{"from": result.range_from},
            to=result.range_to,
        ),
        episodes_by_day_robot=[
            EpisodesByDayRobotResponse(
                date=item.date,
                robot_id=item.robot_id,
                count=item.count,
            )
            for item in result.episodes_by_day_robot
        ],
        requests_by_status=[
            RequestsByStatusResponse(
                status=item.status,
                count=item.count,
            )
            for item in result.requests_by_status
        ],
        median_submitted_to_delivered_hours=(
            result.median_submitted_to_delivered_hours
        ),
        top_tasks_by_good_episodes=[
            TopTaskByGoodEpisodesResponse(
                task_name=item.task_name,
                good_episodes=item.good_episodes,
            )
            for item in result.top_tasks_by_good_episodes
        ],
    )
