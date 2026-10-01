"""align schema with the documented domain contract

Revision ID: d7a4e912c3b5
Revises: cf66b803b67d
Create Date: 2026-10-01 18:10:00.000000
"""

import sqlalchemy as sa
from alembic import op

revision = "d7a4e912c3b5"
down_revision = "cf66b803b67d"
branch_labels = None
depends_on = None


def _to_timestamptz(table_name: str, column_name: str) -> None:
    op.alter_column(
        table_name,
        column_name,
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
    )


def _to_timestamp(table_name: str, column_name: str) -> None:
    op.alter_column(
        table_name,
        column_name,
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
    )


def upgrade() -> None:
    for table_name, column_name in (
        ("users", "created_at"),
        ("users", "updated_at"),
        ("episodes", "recorded_at"),
        ("episodes", "created_at"),
        ("requests", "deadline"),
        ("requests", "created_at"),
        ("requests", "updated_at"),
        ("assignments", "assigned_at"),
        ("request_status_history", "changed_at"),
        ("refresh_tokens", "expires_at"),
        ("refresh_tokens", "created_at"),
    ):
        _to_timestamptz(table_name, column_name)

    op.drop_constraint(
        "request_required_count_positive_check", "requests", type_="check"
    )
    op.drop_constraint("request_quality_filter_check", "requests", type_="check")
    op.alter_column(
        "requests",
        "required_count",
        new_column_name="episodes_requested",
        existing_type=sa.Integer(),
    )
    op.drop_column("requests", "quality_filter")
    op.add_column("requests", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "requests", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column(
        "requests", "status", server_default="submitted", existing_type=sa.String(16)
    )
    op.create_check_constraint(
        "request_episodes_requested_range_check",
        "requests",
        "episodes_requested BETWEEN 1 AND 100000",
    )

    op.alter_column(
        "request_status_history",
        "old_status",
        new_column_name="previous_status",
        existing_type=sa.String(16),
    )
    op.alter_column(
        "request_status_history",
        "notes",
        new_column_name="reason",
        existing_type=sa.String(500),
    )
    op.create_check_constraint(
        "request_status_history_new_status_check",
        "request_status_history",
        "new_status IN "
        "('submitted', 'in_progress', 'delivered', 'rejected', 'accepted')",
    )

    op.alter_column(
        "refresh_tokens",
        "created_at",
        new_column_name="issued_at",
        existing_type=sa.DateTime(timezone=True),
    )
    op.add_column(
        "refresh_tokens", sa.Column("family_id", sa.Uuid(), nullable=True)
    )
    op.execute(
        "UPDATE refresh_tokens SET family_id = gen_random_uuid() "
        "WHERE family_id IS NULL"
    )
    op.alter_column(
        "refresh_tokens", "family_id", nullable=False, existing_type=sa.Uuid()
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "revoked_at")
    op.drop_column("refresh_tokens", "used_at")
    op.drop_column("refresh_tokens", "family_id")
    op.alter_column(
        "refresh_tokens",
        "issued_at",
        new_column_name="created_at",
        existing_type=sa.DateTime(timezone=True),
    )

    op.drop_constraint(
        "request_status_history_new_status_check",
        "request_status_history",
        type_="check",
    )
    op.alter_column(
        "request_status_history",
        "reason",
        new_column_name="notes",
        existing_type=sa.String(500),
    )
    op.alter_column(
        "request_status_history",
        "previous_status",
        new_column_name="old_status",
        existing_type=sa.String(16),
    )

    op.drop_constraint(
        "request_episodes_requested_range_check", "requests", type_="check"
    )
    op.alter_column(
        "requests", "status", server_default=None, existing_type=sa.String(16)
    )
    op.drop_column("requests", "delivered_at")
    op.drop_column("requests", "notes")
    op.add_column(
        "requests",
        sa.Column(
            "quality_filter",
            sa.String(length=16),
            server_default="good",
            nullable=False,
        ),
    )
    op.alter_column(
        "requests", "quality_filter", server_default=None, existing_type=sa.String(16)
    )
    op.alter_column(
        "requests",
        "episodes_requested",
        new_column_name="required_count",
        existing_type=sa.Integer(),
    )
    op.create_check_constraint(
        "request_required_count_positive_check", "requests", "required_count > 0"
    )
    op.create_check_constraint(
        "request_quality_filter_check",
        "requests",
        "quality_filter IN ('good', 'usable', 'bad')",
    )

    for table_name, column_name in (
        ("refresh_tokens", "issued_at"),
        ("refresh_tokens", "expires_at"),
        ("request_status_history", "changed_at"),
        ("assignments", "assigned_at"),
        ("requests", "updated_at"),
        ("requests", "created_at"),
        ("requests", "deadline"),
        ("episodes", "created_at"),
        ("episodes", "recorded_at"),
        ("users", "updated_at"),
        ("users", "created_at"),
    ):
        _to_timestamp(table_name, column_name)
