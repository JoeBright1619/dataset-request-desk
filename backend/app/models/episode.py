import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Episode(Base):
    __tablename__ = "episodes"

    # Columns
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    episode_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    robot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_name: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quality: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "quality IN ('good', 'usable', 'bad')",
            name="episode_quality_check",
        ),
        CheckConstraint(
            "duration_seconds > 0",
            name="episode_duration_positive_check",
        ),
        # Indexes for keyset pagination
        Index(
            "ix_episodes_recorded_at_episode_id",
            recorded_at.desc(),
            episode_id.desc(),
        ),
        Index(
            "ix_episodes_quality_recorded_at_episode_id",
            "quality",
            recorded_at.desc(),
            episode_id.desc(),
        ),
        Index(
            "ix_episodes_task_name_recorded_at_episode_id",
            "task_name",
            recorded_at.desc(),
            episode_id.desc(),
        ),
        Index(
            "ix_episodes_robot_id_recorded_at_episode_id",
            "robot_id",
            recorded_at.desc(),
            episode_id.desc(),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Episode(id={self.id}, episode_id={self.episode_id}, "
            f"task={self.task_name})>"
        )
