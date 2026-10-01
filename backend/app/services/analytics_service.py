"""Business logic for analytics."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.repositories.analytics_repository import (
    AnalyticsRepository,
    EpisodesByDayRobot,
    RequestsByStatus,
    TopTaskByGoodEpisodes,
)


@dataclass(frozen=True)
class AnalyticsResult:
    range_from: datetime
    range_to: datetime
    episodes_by_day_robot: list[EpisodesByDayRobot]
    requests_by_status: list[RequestsByStatus]
    median_submitted_to_delivered_hours: float | None
    top_tasks_by_good_episodes: list[TopTaskByGoodEpisodes]


class AnalyticsService:
    """Coordinate analytics queries and domain validation."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = AnalyticsRepository(session)

    async def get_analytics(
        self,
        range_from: datetime,
        range_to: datetime,
        robot_id: str | None = None,
    ) -> AnalyticsResult:
        if range_from >= range_to:
            raise ValidationError(
                "The 'from' timestamp must be earlier than the 'to' timestamp"
            )

        episodes_by_day_robot = await self._repository.episodes_by_day_robot(
            range_from,
            range_to,
            robot_id,
        )
        requests_by_status = await self._repository.requests_by_status(
            range_from,
            range_to,
        )
        median_submitted_to_delivered_hours = (
            await self._repository.median_submitted_to_delivered_hours(
                range_from,
                range_to,
            )
        )
        top_tasks_by_good_episodes = await self._repository.top_tasks_by_good_episodes(
            range_from,
            range_to,
            robot_id,
        )

        return AnalyticsResult(
            range_from=range_from,
            range_to=range_to,
            episodes_by_day_robot=episodes_by_day_robot,
            requests_by_status=requests_by_status,
            median_submitted_to_delivered_hours=median_submitted_to_delivered_hours,
            top_tasks_by_good_episodes=top_tasks_by_good_episodes,
        )
