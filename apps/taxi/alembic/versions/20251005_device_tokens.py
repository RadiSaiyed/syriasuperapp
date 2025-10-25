"""add device_tokens table

Revision ID: 20251005_device_tokens
Revises: 20251005_accepted_at
Create Date: 2025-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20251005_device_tokens'
down_revision = '20251005_accepted_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if 'device_tokens' not in insp.get_table_names():
        op.create_table(
            'device_tokens',
            sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('platform', sa.String(length=16), nullable=False),
            sa.Column('token', sa.String(length=256), nullable=False),
            sa.Column('app_mode', sa.String(length=16), nullable=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('last_seen', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_dev_token_user', 'device_tokens', ['user_id'])
        op.create_index('ix_dev_token_token', 'device_tokens', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_dev_token_token', table_name='device_tokens')
    op.drop_index('ix_dev_token_user', table_name='device_tokens')
    op.drop_table('device_tokens')
