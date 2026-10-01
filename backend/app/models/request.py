import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Request(Base):
    __tablename__ = "requests"

    # Columns
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    episodes_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="submitted", server_default="submitted", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', "
            "'rejected', 'accepted')",
            name="request_status_check",
        ),
        CheckConstraint(
            "episodes_requested BETWEEN 1 AND 100000",
            name="request_episodes_requested_range_check",
        ),
        # Indexes for keyset pagination
        Index(
            "ix_requests_created_at_id",
            created_at.desc(),
            id.desc(),
        ),
        Index(
            "ix_requests_client_id_created_at_id",
            "client_id",
            created_at.desc(),
            id.desc(),
        ),
        Index(
            "ix_requests_status_created_at_id",
            "status",
            created_at.desc(),
            id.desc(),
        ),
    )

    def __repr__(self) -> str:
        return f"<Request(id={self.id}, task={self.task_name}, status={self.status})>"
