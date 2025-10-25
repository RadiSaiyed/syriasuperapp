"""
payments enhancements: indices, audit, webhooks, api keys, fee_bps

Revision ID: 9f0eaddf1abc
Revises: 71eba1297e5d
Create Date: 2025-09-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '9f0eaddf1abc'
down_revision = '71eba1297e5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merchants.fee_bps
    with op.batch_alter_table('merchants') as batch_op:
        batch_op.add_column(sa.Column('fee_bps', sa.Integer(), nullable=True))

    # cash_requests idempotency unique
    try:
        op.create_unique_constraint('uq_cash_requests_idem', 'cash_requests', ['idempotency_key'])
    except Exception:
        pass

    # payment_requests indices + idempotency unique
    try:
        op.create_unique_constraint('uq_payment_requests_idem', 'payment_requests', ['idempotency_key'])
    except Exception:
        pass
    try:
        op.create_index('ix_pr_target_created', 'payment_requests', ['target_user_id', 'created_at'], unique=False)
    except Exception:
        pass
    try:
        op.create_index('ix_pr_requester_created', 'payment_requests', ['requester_user_id', 'created_at'], unique=False)
    except Exception:
        pass

    # audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # merchant_api_keys
    op.create_table(
        'merchant_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key_id', sa.String(length=32), nullable=False),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('scope', sa.String(length=128), nullable=True),
    )
    op.create_index(op.f('ix_merchant_api_keys_key_id'), 'merchant_api_keys', ['key_id'], unique=True)

    # webhooks
    op.create_table(
        'webhook_endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.String(length=512), nullable=False),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_webhook_deliveries_endpoint_id'), 'webhook_deliveries', ['endpoint_id'], unique=False)


def downgrade() -> None:
    # Drop webhook tables
    op.drop_index(op.f('ix_webhook_deliveries_endpoint_id'), table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhook_endpoints')

    # Drop merchant_api_keys
    op.drop_index(op.f('ix_merchant_api_keys_key_id'), table_name='merchant_api_keys')
    op.drop_table('merchant_api_keys')

    # Drop audit_events
    op.drop_table('audit_events')

    # Drop payment_requests extras
    try:
        op.drop_index('ix_pr_requester_created', table_name='payment_requests')
    except Exception:
        pass
    try:
        op.drop_index('ix_pr_target_created', table_name='payment_requests')
    except Exception:
        pass
    try:
        op.drop_constraint('uq_payment_requests_idem', 'payment_requests', type_='unique')
    except Exception:
        pass

    # Drop cash_requests unique
    try:
        op.drop_constraint('uq_cash_requests_idem', 'cash_requests', type_='unique')
    except Exception:
        pass

    # Drop merchants.fee_bps
    with op.batch_alter_table('merchants') as batch_op:
        try:
            batch_op.drop_column('fee_bps')
        except Exception:
            pass
