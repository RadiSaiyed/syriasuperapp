"""
Amount and integrity checks on monetary tables

Revision ID: 20251026_01
Revises: 20250930_01
Create Date: 2025-10-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251026_01'
down_revision = '20250930_01'
branch_labels = None
depends_on = None


def _create_check(name: str, table: str, condition: str) -> None:
    try:
        op.create_check_constraint(name, table, condition)
    except Exception:
        # Ignore if exists or DB differences
        pass


def _drop_check(name: str, table: str) -> None:
    try:
        op.drop_constraint(name, table_name=table, type_='check')
    except Exception:
        pass


def upgrade() -> None:
    # Positive amounts where applicable
    _create_check('ck_transfers_amount_positive', 'transfers', 'amount_cents > 0')
    _create_check('ck_refunds_amount_positive', 'refunds', 'amount_cents > 0')
    _create_check('ck_cash_requests_amount_positive', 'cash_requests', 'amount_cents > 0')
    _create_check('ck_subscriptions_amount_positive', 'subscriptions', 'amount_cents > 0')
    _create_check('ck_invoices_amount_positive', 'invoices', 'amount_cents > 0')
    # Create check on topup_vouchers only if table exists (fresh DBs may not have it in older chains)
    try:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        if 'topup_vouchers' in inspector.get_table_names():
            _create_check('ck_topup_vouchers_amount_positive', 'topup_vouchers', 'amount_cents > 0')
    except Exception:
        pass

    # Ledger entries must be non-zero to avoid no-op rows
    _create_check('ck_ledger_amount_nonzero', 'ledger_entries', 'amount_cents_signed <> 0')


def downgrade() -> None:
    _drop_check('ck_ledger_amount_nonzero', 'ledger_entries')
    try:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        if 'topup_vouchers' in inspector.get_table_names():
            _drop_check('ck_topup_vouchers_amount_positive', 'topup_vouchers')
    except Exception:
        pass
    _drop_check('ck_invoices_amount_positive', 'invoices')
    _drop_check('ck_subscriptions_amount_positive', 'subscriptions')
    _drop_check('ck_cash_requests_amount_positive', 'cash_requests')
    _drop_check('ck_refunds_amount_positive', 'refunds')
    _drop_check('ck_transfers_amount_positive', 'transfers')
