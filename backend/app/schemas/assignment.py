"""HTTP request and response schemas for assignments."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssignmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: str
    robot_id: str
    task_name: str
    quality: str
    recorded_at: datetime
    assigned_at: datetime
    assigned_by: UUID


class AssignmentListResponse(BaseModel):
    items: list[AssignmentItemResponse]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    has_prev: bool = False
    limit: int


class AssignmentBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episode_ids: list[str] = Field(min_length=1, max_length=500)


RejectionReasonSchema = Literal[
    "not_found",
    "invalid_quality",
    "already_assigned",
]


class RejectedAssignmentResponse(BaseModel):
    episode_id: str
    reason: RejectionReasonSchema


class AssignmentBatchResponse(BaseModel):
    request_id: UUID
    assigned: list[str]
    rejected: list[RejectedAssignmentResponse]
    episodes_requested: int
    episodes_assigned: int
