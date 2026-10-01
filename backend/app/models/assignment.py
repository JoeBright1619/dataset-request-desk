import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Assignment(Base):
    __tablename__ = "assignments"

    # Columns
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    release_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Indexes and constraints
    __table_args__ = (
        # Regular indexes
        Index(
            "ix_assignments_request_id_assigned_at_episode_id",
            "request_id",
            "assigned_at",
            "episode_id",
            postgresql_ops={"assigned_at": "DESC", "episode_id": "DESC"},
        ),
        Index(
            "ix_assignments_assigned_at_episode_id",
            "assigned_at",
            "episode_id",
            postgresql_ops={"assigned_at": "DESC", "episode_id": "DESC"},
        ),
        # **CRITICAL: Partial unique index** - only one active assignment per episode
        Index(
            "ix_assignments_episode_id_active",
            "episode_id",
            unique=True,
            postgresql_where="released_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        released = self.released_at is not None
        return (
            f"<Assignment(id={self.id}, request_id={self.request_id}, "
            f"episode_id={self.episode_id}, released={released})>"
        )
