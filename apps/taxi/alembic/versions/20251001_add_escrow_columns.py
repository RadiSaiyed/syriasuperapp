"""add escrow columns to rides

Revision ID: 20251001_add_escrow
Revises: 
Create Date: 2025-10-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20251001_add_escrow'
down_revision = '20251000_init_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('rides')}
    with op.batch_alter_table('rides') as batch:
        if 'escrow_amount_cents' not in cols:
            batch.add_column(sa.Column('escrow_amount_cents', sa.Integer(), nullable=True))
        if 'escrow_released' not in cols:
            batch.add_column(sa.Column('escrow_released', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    with op.batch_alter_table('rides') as batch:
        batch.drop_column('escrow_released')
        batch.drop_column('escrow_amount_cents')
