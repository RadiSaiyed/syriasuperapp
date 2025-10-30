"""add idempotency_keys table with request fingerprint

Revision ID: 20251029_01
Revises: 20251026_01
Create Date: 2025-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20251029_01'
down_revision = '20251026_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'idempotency_keys',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('method', sa.String(length=8), nullable=False),
        sa.Column('path', sa.String(length=256), nullable=False),
        sa.Column('body_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='in_progress'),
        sa.Column('result_ref', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'key', name='uq_idem_user_key'),
    )
    op.create_index('ix_idem_user_created', 'idempotency_keys', ['user_id', 'created_at'])
    op.execute("ALTER TABLE idempotency_keys ALTER COLUMN status DROP DEFAULT")


def downgrade() -> None:
    op.drop_index('ix_idem_user_created', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')

