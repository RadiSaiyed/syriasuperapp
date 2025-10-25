"""add beneficiary fields and payer mode to rides

Revision ID: 20251006_benef_paymode
Revises: 20251005_eta_predicted
Create Date: 2025-10-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20251006_benef_paymode'
down_revision = '20251005_eta_predicted'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('rides')}
    with op.batch_alter_table('rides') as batch:
        if 'passenger_name' not in cols:
            batch.add_column(sa.Column('passenger_name', sa.String(length=128), nullable=True))
        if 'passenger_phone' not in cols:
            batch.add_column(sa.Column('passenger_phone', sa.String(length=32), nullable=True))
        if 'payer_mode' not in cols:
            batch.add_column(sa.Column('payer_mode', sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('rides') as batch:
        batch.drop_column('payer_mode')
        batch.drop_column('passenger_phone')
        batch.drop_column('passenger_name')
