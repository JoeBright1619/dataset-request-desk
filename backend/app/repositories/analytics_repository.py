"""Database-side aggregations for the analytics endpoint."""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Date, Float, func, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.models.request import Request


@dataclass(frozen=True)
class EpisodesByDayRobot:
    date: date
    robot_id: str
    count: int


@dataclass(frozen=True)
class RequestsByStatus:
    status: str
    count: int


@dataclass(frozen=True)
class TopTaskByGoodEpisodes:
    task_name: str
    good_episodes: int


class AnalyticsRepository:
    """Run each analytics aggregation in one SQL query."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def episodes_by_day_robot(
        self, range_from: datetime, range_to: datetime, robot_id: str | None = None
    ) -> list[EpisodesByDayRobot]:
        recorded_date = sql_cast(Episode.recorded_at, Date).label("recorded_date")
        statement = (
            select(
                recorded_date,
                Episode.robot_id,
                func.count(Episode.id).label("episode_count"),
            )
            .where(Episode.recorded_at >= range_from, Episode.recorded_at < range_to)
            .group_by(recorded_date, Episode.robot_id)
            .order_by(recorded_date, Episode.robot_id)
        )
        if robot_id is not None:
            statement = statement.where(Episode.robot_id == robot_id)

        rows = (await self._session.execute(statement)).tuples().all()
        return [
            EpisodesByDayRobot(
                date=row[0],
                robot_id=row[1],
                count=row[2],
            )
            for row in rows
        ]

    async def requests_by_status(
        self, range_from: datetime, range_to: datetime
    ) -> list[RequestsByStatus]:
        statement = (
            select(Request.status, func.count(Request.id).label("request_count"))
            .where(Request.created_at >= range_from, Request.created_at < range_to)
            .group_by(Request.status)
            .order_by(Request.status)
        )
        rows = (await self._session.execute(statement)).tuples().all()
        return [RequestsByStatus(status=row[0], count=row[1]) for row in rows]

    async def median_submitted_to_delivered_hours(
        self, range_from: datetime, range_to: datetime
    ) -> float | None:
        duration_hours = sql_cast(
            func.extract("epoch", Request.delivered_at - Request.created_at) / 3600,
            Float,
        )
        statement = select(
            func.percentile_cont(0.5).within_group(duration_hours).label("median_hours")
        ).where(
            Request.delivered_at.is_not(None),
            Request.delivered_at >= range_from,
            Request.delivered_at < range_to,
        )
        median: float | None = (await self._session.execute(statement)).scalar_one()
        return float(median) if median is not None else None

    async def top_tasks_by_good_episodes(
        self, range_from: datetime, range_to: datetime, robot_id: str | None = None
    ) -> list[TopTaskByGoodEpisodes]:
        statement = (
            select(
                Episode.task_name,
                func.count(Episode.id).label("good_episode_count"),
            )
            .where(
                Episode.quality == "good",
                Episode.recorded_at >= range_from,
                Episode.recorded_at < range_to,
            )
            .group_by(Episode.task_name)
            .order_by(func.count(Episode.id).desc(), Episode.task_name)
            .limit(5)
        )
        if robot_id is not None:
            statement = statement.where(Episode.robot_id == robot_id)

        rows = (await self._session.execute(statement)).tuples().all()
        return [
            TopTaskByGoodEpisodes(
                task_name=row[0],
                good_episodes=row[1],
            )
            for row in rows
        ]
