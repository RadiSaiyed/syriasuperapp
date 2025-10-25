"""add subscriptions table

Revision ID: 20250929_04
Revises: 20250929_03
Create Date: 2025-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20250929_04'
down_revision = '20250929_03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payer_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('merchant_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency_code', sa.String(length=8), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('next_charge_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_sub_payer_status', 'subscriptions', ['payer_user_id', 'status'])
    op.create_index('ix_sub_next_charge', 'subscriptions', ['next_charge_at'])
    op.execute("ALTER TABLE subscriptions ALTER COLUMN interval_days DROP DEFAULT")
    op.execute("ALTER TABLE subscriptions ALTER COLUMN status DROP DEFAULT")


def downgrade() -> None:
    op.drop_index('ix_sub_next_charge', table_name='subscriptions')
    op.drop_index('ix_sub_payer_status', table_name='subscriptions')
    op.drop_table('subscriptions')

