"""add invoices and ebill mandates

Revision ID: 20250930_01
Revises: 20250929_04
Create Date: 2025-09-30
"""

from alembic import op
import sqlalchemy as sa


revision = '20250930_01'
down_revision = '20250929_04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ebill_mandates
    op.create_table(
        'ebill_mandates',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('payer_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('issuer_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('autopay', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('max_amount_cents', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('payer_user_id', 'issuer_user_id', name='uq_ebill_mandate_pair'),
    )
    op.create_index('ix_ebill_mandate_payer', 'ebill_mandates', ['payer_user_id'])
    op.execute("ALTER TABLE ebill_mandates ALTER COLUMN autopay DROP DEFAULT")
    op.execute("ALTER TABLE ebill_mandates ALTER COLUMN status DROP DEFAULT")

    # invoices
    op.create_table(
        'invoices',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('issuer_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('payer_user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('currency_code', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('reference', sa.String(length=128), nullable=True),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('due_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('paid_transfer_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('transfers.id'), nullable=True),
    )
    op.create_index('ix_invoice_payer_status', 'invoices', ['payer_user_id', 'status'])
    op.create_index('ix_invoice_due_at', 'invoices', ['due_at'])
    op.execute("ALTER TABLE invoices ALTER COLUMN status DROP DEFAULT")


def downgrade() -> None:
    op.drop_index('ix_invoice_due_at', table_name='invoices')
    op.drop_index('ix_invoice_payer_status', table_name='invoices')
    op.drop_table('invoices')
    op.drop_index('ix_ebill_mandate_payer', table_name='ebill_mandates')
    op.drop_table('ebill_mandates')

