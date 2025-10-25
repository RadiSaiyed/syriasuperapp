"""add payment_links and qr mode

Revision ID: 20250929_03
Revises: 20250929_02
Create Date: 2025-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20250929_03'
down_revision = '20250929_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # qr_codes add mode
    with op.batch_alter_table('qr_codes') as batch:
        batch.add_column(sa.Column('mode', sa.String(length=16), nullable=False, server_default='dynamic'))
    op.execute("ALTER TABLE qr_codes ALTER COLUMN mode DROP DEFAULT")

    # payment_links
    op.create_table(
        'payment_links',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('code', sa.String(length=128), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency_code', sa.String(length=8), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('code', name='uq_links_code'),
    )
    op.create_index('ix_links_user_created', 'payment_links', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_links_user_created', table_name='payment_links')
    op.drop_table('payment_links')
    with op.batch_alter_table('qr_codes') as batch:
        batch.drop_column('mode')

