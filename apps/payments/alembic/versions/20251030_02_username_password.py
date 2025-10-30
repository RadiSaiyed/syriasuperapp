"""add username + password_hash to users

Revision ID: 20251030_02_username_password
Revises: 20251029_01
Create Date: 2025-10-30 12:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251030_02_username_password'
down_revision = '20251029_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=128), nullable=True))
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'username')
