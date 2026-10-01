"""update users schema to use email name and organisation

Revision ID: 3caf820a0b4e
Revises: 08ab3cf702b8
Create Date: 2026-10-01 15:51:27.756412

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3caf820a0b4e'
down_revision = '08ab3cf702b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete all existing users (dev environment only - old username-based users)
    # This is safe because we're changing the fundamental identity field
    op.execute('DELETE FROM users')
    
    # Add new columns
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=False))
    op.add_column('users', sa.Column('name', sa.String(length=128), nullable=False))
    op.add_column('users', sa.Column('organisation', sa.String(length=128), nullable=True))
    
    # Create unique constraint on email
    op.create_unique_constraint('users_email_key', 'users', ['email'])
    
    # Drop the old unique constraint on username
    op.drop_constraint('users_username_key', 'users', type_='unique')
    
    # Drop the username column
    op.drop_column('users', 'username')


def downgrade() -> None:
    # Add username back
    op.add_column('users', sa.Column('username', sa.String(length=64), nullable=True))
    
    # Make username NOT NULL
    op.alter_column('users', 'username', nullable=False)
    
    # Restore unique constraint on username
    op.create_unique_constraint('users_username_key', 'users', ['username'])
    
    # Make email and name nullable
    op.alter_column('users', 'name', nullable=True)
    op.alter_column('users', 'email', nullable=True)
    
    # Drop unique constraint on email
    op.drop_constraint('users_email_key', 'users', type_='unique')
    
    # Drop new columns
    op.drop_column('users', 'organisation')
    op.drop_column('users', 'name')
    op.drop_column('users', 'email')
