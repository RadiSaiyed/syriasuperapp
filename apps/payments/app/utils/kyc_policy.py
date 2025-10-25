from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config import settings
from ..models import User, Wallet, LedgerEntry


def _start_of_day_utc(dt: datetime | None = None) -> datetime:
    now = dt or datetime.utcnow()
    return datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc).replace(tzinfo=None)


def _limits_for_level(level: int) -> tuple[int, int]:
    if level >= 1:
        return settings.KYC_L1_TX_MAX_CENTS, settings.KYC_L1_DAILY_MAX_CENTS
    return settings.KYC_L0_TX_MAX_CENTS, settings.KYC_L0_DAILY_MAX_CENTS


def enforce_tx_limits(db: Session, user: User, amount_cents: int):
    if amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")

    tx_max, daily_max = _limits_for_level(user.kyc_level)
    if amount_cents > tx_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KYC transaction limit exceeded")

    # Sum today's outgoing for this wallet
    wallet: Wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    start = _start_of_day_utc()
    outgoing_today = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount_cents_signed), 0))
        .filter(LedgerEntry.wallet_id == wallet.id)
        .filter(LedgerEntry.amount_cents_signed < 0)
        .filter(LedgerEntry.created_at >= start)
        .scalar()
    )
    projected = abs(outgoing_today) + amount_cents
    if projected > daily_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KYC daily limit exceeded")


def require_min_kyc_level(user: User, min_level: int):
    if user.kyc_level < min_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="KYC level required")

