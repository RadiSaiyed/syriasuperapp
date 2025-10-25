#!/usr/bin/env python3
"""
Reconciliation checks for Payments ledger consistency.

Usage:
  DB_URL=postgresql+psycopg2://... python apps/payments/scripts/reconcile.py [--fix-balances]

Checks:
- Wallet balances equal the sum of their ledger entries
- Transfers with both from_wallet_id and to_wallet_id have 2 entries: -amount and +amount
- Topups (from_wallet_id is NULL) have 1 entry on the destination wallet for +amount

With --fix-balances, updates wallet.balance_cents to match ledger sums.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.models import Wallet, LedgerEntry, Transfer  # type: ignore  # noqa: E402


DB_URL = os.getenv("DB_URL")
if not DB_URL:
    print("Set DB_URL env to point to the payments database", file=sys.stderr)
    sys.exit(2)


engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)


@dataclass
class WalletMismatch:
    wallet_id: str
    balance: int
    ledger_sum: int


def check_wallet_balances(session) -> List[WalletMismatch]:
    mismatches: List[WalletMismatch] = []
    # Sum ledger per wallet
    sums = dict(
        session.query(LedgerEntry.wallet_id, func.coalesce(func.sum(LedgerEntry.amount_cents_signed), 0))
        .group_by(LedgerEntry.wallet_id)
        .all()
    )
    for w in session.query(Wallet).all():
        s = int(sums.get(w.id, 0))
        if int(w.balance_cents) != s:
            mismatches.append(WalletMismatch(wallet_id=str(w.id), balance=int(w.balance_cents), ledger_sum=s))
    return mismatches


@dataclass
class TransferIssue:
    transfer_id: str
    problem: str
    details: str


def check_transfers(session) -> List[TransferIssue]:
    issues: List[TransferIssue] = []
    # Iterate transfers in manageable chunks
    q = session.query(Transfer).order_by(Transfer.created_at.asc())
    for t in q:
        entries = session.query(LedgerEntry).filter(LedgerEntry.transfer_id == t.id).all()
        if t.from_wallet_id is not None and t.to_wallet_id is not None:
            if len(entries) != 2:
                issues.append(TransferIssue(str(t.id), "entries_count", f"expected 2, got {len(entries)}"))
                continue
            amounts = sorted(int(e.amount_cents_signed) for e in entries)
            if amounts != [-int(t.amount_cents), int(t.amount_cents)]:
                issues.append(TransferIssue(str(t.id), "amount_mismatch", f"entries={amounts}, transfer={t.amount_cents}"))
        elif t.from_wallet_id is None and t.to_wallet_id is not None:
            if len(entries) != 1:
                issues.append(TransferIssue(str(t.id), "entries_count_topup", f"expected 1, got {len(entries)}"))
                continue
            if int(entries[0].amount_cents_signed) != int(t.amount_cents) or entries[0].wallet_id != t.to_wallet_id:
                issues.append(
                    TransferIssue(
                        str(t.id),
                        "topup_mismatch",
                        f"entry={{amt={entries[0].amount_cents_signed}, wallet={entries[0].wallet_id}}} vs transfer amt={t.amount_cents}, to_wallet={t.to_wallet_id}",
                    )
                )
        else:
            # Unsupported/unknown pattern in current MVP; flag it
            issues.append(TransferIssue(str(t.id), "unsupported_pattern", f"from={t.from_wallet_id} to={t.to_wallet_id}"))
    return issues


def main() -> int:
    fix = "--fix-balances" in sys.argv
    with Session() as session:
        mismatches = check_wallet_balances(session)
        issues = check_transfers(session)
        print(f"Wallet mismatches: {len(mismatches)}")
        for m in mismatches[:50]:
            print(f"  wallet={m.wallet_id} balance={m.balance} ledger_sum={m.ledger_sum}")
        if len(mismatches) > 50:
            print(f"  ... and {len(mismatches) - 50} more")

        print(f"Transfer issues: {len(issues)}")
        for i in issues[:50]:
            print(f"  transfer={i.transfer_id} problem={i.problem} details={i.details}")
        if len(issues) > 50:
            print(f"  ... and {len(issues) - 50} more")

        if fix and mismatches:
            for m in mismatches:
                session.query(Wallet).filter(Wallet.id == m.wallet_id).update({Wallet.balance_cents: m.ledger_sum})
            session.commit()
            print(f"Updated {len(mismatches)} wallet balances to match ledger sums.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

