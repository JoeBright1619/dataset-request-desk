import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RequestStatusHistory(Base):
    __tablename__ = "request_status_history"

    # Columns
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    new_status: Mapped[str] = mapped_column(String(16), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Indexes
    __table_args__ = (
        CheckConstraint(
            "new_status IN "
            "('submitted', 'in_progress', 'delivered', 'rejected', 'accepted')",
            name="request_status_history_new_status_check",
        ),
        Index(
            "ix_request_status_history_request_id_changed_at",
            "request_id",
            changed_at.desc(),
        ),
        Index(
            "ix_request_status_history_changed_at",
            changed_at.desc(),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RequestStatusHistory(id={self.id}, "
            f"request_id={self.request_id}, "
            f"{self.previous_status} → {self.new_status})>"
        )
