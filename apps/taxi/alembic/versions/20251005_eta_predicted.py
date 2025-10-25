"""add eta_pickup_predicted_mins

Revision ID: 20251005_eta_predicted
Revises: 20251005_device_tokens
Create Date: 2025-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20251005_eta_predicted'
down_revision = '20251005_device_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('rides')}
    with op.batch_alter_table('rides') as batch:
        if 'eta_pickup_predicted_mins' not in cols:
            batch.add_column(sa.Column('eta_pickup_predicted_mins', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('rides') as batch:
        batch.drop_column('eta_pickup_predicted_mins')
