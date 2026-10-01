"""HTTP schemas for analytics responses."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: datetime = Field(alias="from")
    to: datetime


class EpisodesByDayRobotResponse(BaseModel):
    date: date
    robot_id: str
    count: int


class RequestsByStatusResponse(BaseModel):
    status: str
    count: int


class TopTaskByGoodEpisodesResponse(BaseModel):
    task_name: str
    good_episodes: int


class AnalyticsResponse(BaseModel):
    range: AnalyticsRange
    episodes_by_day_robot: list[EpisodesByDayRobotResponse]
    requests_by_status: list[RequestsByStatusResponse]
    median_submitted_to_delivered_hours: float | None
    top_tasks_by_good_episodes: list[TopTaskByGoodEpisodesResponse]
