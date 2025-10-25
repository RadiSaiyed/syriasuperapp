"""extend payment_requests and webhook_deliveries

Revision ID: 20250929_01
Revises: 9f0eaddf1abc
Create Date: 2025-09-29
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250929_01'
down_revision = '9f0eaddf1abc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # payment_requests: add expires_at, metadata_json
    with op.batch_alter_table('payment_requests') as batch:
        batch.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('metadata_json', sa.JSON(), nullable=True))

    # webhook_deliveries: add last_attempt_at, next_attempt_at
    with op.batch_alter_table('webhook_deliveries') as batch:
        batch.add_column(sa.Column('last_attempt_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('next_attempt_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('webhook_deliveries') as batch:
        batch.drop_column('next_attempt_at')
        batch.drop_column('last_attempt_at')

    with op.batch_alter_table('payment_requests') as batch:
        batch.drop_column('metadata_json')
        batch.drop_column('expires_at')

