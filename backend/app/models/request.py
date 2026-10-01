import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, func
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
    required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_filter: Mapped[str] = mapped_column(String(16), nullable=False)
    deadline: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', "
            "'rejected', 'accepted')",
            name="request_status_check",
        ),
        CheckConstraint(
            "quality_filter IN ('good', 'usable', 'bad')",
            name="request_quality_filter_check",
        ),
        CheckConstraint(
            "required_count > 0",
            name="request_required_count_positive_check",
        ),
        # Indexes for keyset pagination
        Index(
            "ix_requests_created_at_id",
            "created_at",
            "id",
            postgresql_ops={"created_at": "DESC", "id": "DESC"},
        ),
        Index(
            "ix_requests_client_id_created_at_id",
            "client_id",
            "created_at",
            "id",
            postgresql_ops={"created_at": "DESC", "id": "DESC"},
        ),
        Index(
            "ix_requests_status_created_at_id",
            "status",
            "created_at",
            "id",
            postgresql_ops={"created_at": "DESC", "id": "DESC"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Request(id={self.id}, task={self.task_name}, status={self.status})>"
