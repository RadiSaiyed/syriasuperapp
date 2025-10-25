"""add accepted_at to rides

Revision ID: 20251005_accepted_at
Revises: 
Create Date: 2025-10-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20251005_accepted_at'
down_revision = '20251001_add_escrow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c['name'] for c in insp.get_columns('rides')}
    with op.batch_alter_table('rides') as batch_op:
        if 'accepted_at' not in cols:
            batch_op.add_column(sa.Column('accepted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('rides') as batch_op:
        batch_op.drop_column('accepted_at')
