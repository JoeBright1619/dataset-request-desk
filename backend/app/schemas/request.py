"""HTTP request and response schemas for dataset requests."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

RequestStatus = Literal[
    "submitted",
    "in_progress",
    "delivered",
    "accepted",
    "rejected",
]


class RequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_name: str = Field(min_length=1, max_length=128)
    episodes_requested: int = Field(ge=1, le=100000)
    deadline: datetime
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("deadline")
    @classmethod
    def validate_deadline_in_future(cls, value: datetime) -> datetime:
        now = datetime.now(value.tzinfo) if value.tzinfo else datetime.utcnow()
        if value <= now:
            raise ValueError("deadline must be in the future")
        return value


class RequestStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RequestStatus
    reason: str | None = Field(default=None, max_length=500)


class RequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    client_name: str
    task_name: str
    episodes_requested: int
    episodes_assigned: int
    deadline: datetime
    notes: str | None
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None


class RequestListResponse(BaseModel):
    items: list[RequestResponse]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    has_prev: bool = False
    limit: int
