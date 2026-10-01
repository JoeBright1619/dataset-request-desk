"""make assignments.released_at timezone-aware

Revision ID: cf66b803b67d
Revises: 3caf820a0b4e
Create Date: 2026-10-01 16:56:19.886128

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf66b803b67d'
down_revision = '3caf820a0b4e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "assignments",
        "released_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="released_at AT TIME ZONE 'UTC'",
    )

def downgrade():
    op.alter_column(
        "assignments",
        "released_at",
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        postgresql_using="released_at AT TIME ZONE 'UTC'",
    )