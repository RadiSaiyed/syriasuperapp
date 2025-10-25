#!/usr/bin/env python3
"""
Generate a simple merchant settlement CSV for a given time range.

Usage:
  DB_URL=postgresql+psycopg2://... python apps/payments/scripts/settlement_report.py --from 2025-09-01T00:00:00Z --to 2025-09-30T23:59:59Z > settlement.csv

Columns:
  merchant_user_id, merchant_wallet_id, currency, gross_cents, fees_cents, net_cents
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.models import Transfer, Merchant, Wallet  # type: ignore  # noqa: E402
from app.utils.fees import ensure_fee_wallet  # type: ignore  # noqa: E402


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        raise SystemExit(f"Invalid timestamp: {s}")


def main() -> int:
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("Set DB_URL env to point to the payments database", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_ts", help="ISO8601 start time (UTC)")
    ap.add_argument("--to", dest="to_ts", help="ISO8601 end time (UTC)")
    args = ap.parse_args()

    to_dt = parse_ts(args.to_ts) or datetime.utcnow()
    from_dt = parse_ts(args.from_ts) or (to_dt - timedelta(days=1))

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        fee_wallet = ensure_fee_wallet(session)
        print("merchant_user_id,merchant_wallet_id,currency,gross_cents,fees_cents,net_cents")
        for m in session.query(Merchant).all():
            mw = session.query(Wallet).filter(Wallet.id == m.wallet_id).one()
            income = (
                session.query(Transfer)
                .filter(
                    Transfer.to_wallet_id == mw.id,
                    Transfer.created_at >= from_dt,
                    Transfer.created_at <= to_dt,
                )
                .all()
            )
            gross = sum(int(t.amount_cents) for t in income)
            fees = (
                session.query(Transfer)
                .filter(
                    Transfer.from_wallet_id == mw.id,
                    Transfer.to_wallet_id == fee_wallet.id,
                    Transfer.created_at >= from_dt,
                    Transfer.created_at <= to_dt,
                )
                .all()
            )
            fee_sum = sum(int(t.amount_cents) for t in fees)
            net = gross - fee_sum
            print(f"{m.user_id},{mw.id},{mw.currency_code},{gross},{fee_sum},{net}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

