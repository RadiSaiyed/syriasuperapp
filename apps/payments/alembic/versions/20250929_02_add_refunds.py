"""add refunds table

Revision ID: 20250929_02
Revises: 20250929_01
Create Date: 2025-09-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250929_02'
down_revision = '20250929_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'refunds',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_transfer_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('transfers.id'), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency_code', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('idempotency_key', name='uq_refunds_idem'),
    )
    op.create_index('ix_refunds_original_created', 'refunds', ['original_transfer_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_refunds_original_created', table_name='refunds')
    op.drop_table('refunds')

