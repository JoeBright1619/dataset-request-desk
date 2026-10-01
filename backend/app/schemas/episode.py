"""HTTP schemas for episode search and detail responses."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

EpisodeQuality = Literal["good", "usable", "bad"]


class EpisodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: datetime
    duration_seconds: Decimal
    operator_name: str | None
    quality: EpisodeQuality
    is_assigned: bool
    created_at: datetime


class EpisodeListResponse(BaseModel):
    items: list[EpisodeResponse]
    next_cursor: str | None
    prev_cursor: str | None
    has_more: bool
    has_prev: bool
    limit: int
