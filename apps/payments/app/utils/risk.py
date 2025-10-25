from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from ..models import User, Merchant
from ..utils.audit import record_event
from fastapi import HTTPException, status


def _getint(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def evaluate_risk_and_maybe_block(
    db: Session,
    user: User,
    amount_cents: int,
    context: str,
    merchant_user_id: Optional[str] = None,
):
    if os.getenv("FRAUD_RISK_ENABLED", "false").lower() != "true":
        return
    score = 0
    factors: list[str] = []

    # Account age
    age_days = (datetime.utcnow() - (user.created_at or datetime.utcnow())).days
    if age_days < 1:
        score += 30; factors.append("new_account")
    elif age_days < 7:
        score += 10; factors.append("young_account")

    # KYC level
    try:
        kyc = int(getattr(user, "kyc_level", 0) or 0)
    except Exception:
        kyc = 0
    if kyc <= 0:
        score += 20; factors.append("kyc_l0")
    elif kyc == 1:
        score += 5; factors.append("kyc_l1")

    # Amount
    high_amt = _getint("FRAUD_HIGH_AMOUNT_CENTS", 2_000_000)  # 20,000.00 SYP
    if amount_cents >= high_amt:
        score += 25; factors.append("high_amount")

    # Night time (UTC)
    hour = datetime.utcnow().hour
    if hour < 6:
        score += 10; factors.append("night")

    # New merchant (if receiving)
    if merchant_user_id is not None:
        m_user = db.get(User, merchant_user_id)
        if m_user and getattr(m_user, "is_merchant", False):
            merchant = db.query(Merchant).filter(Merchant.user_id == m_user.id).one_or_none()
            if merchant and (datetime.utcnow() - merchant.created_at) < timedelta(days=7):
                score += 10; factors.append("new_merchant")

    flag_thr = _getint("FRAUD_FLAG_SCORE", 60)
    block_thr = _getint("FRAUD_BLOCK_SCORE", 100)

    data = {"context": context, "amount_cents": amount_cents, "score": score, "factors": factors}
    if score >= block_thr:
        record_event(db, "fraud.block", str(user.id), data)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="risk_blocked")
    if score >= flag_thr:
        record_event(db, "fraud.flag", str(user.id), data)
    return

