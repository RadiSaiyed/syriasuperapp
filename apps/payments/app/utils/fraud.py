from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Wallet, Transfer
from ..config import settings
from fastapi import HTTPException, status


# Config defaults via env (optional):
# FRAUD_P2P_MAX_TX_PER_HOUR, FRAUD_P2P_MAX_SUM_PER_HOUR
# FRAUD_QR_MAX_TX_PER_HOUR

def _cfg_int(name: str, default: int) -> int:
    import os
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def check_p2p_velocity(db: Session, user, amount_cents: int):
    max_tx = _cfg_int("FRAUD_P2P_MAX_TX_PER_HOUR", 100)
    max_sum = _cfg_int("FRAUD_P2P_MAX_SUM_PER_HOUR", 10_000_000)  # 100,000.00 SYP
    since = datetime.utcnow() - timedelta(hours=1)
    w = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    q = (
        db.query(func.count(Transfer.id), func.coalesce(func.sum(Transfer.amount_cents), 0))
        .filter(Transfer.from_wallet_id == w.id, Transfer.created_at >= since)
        .one()
    )
    cnt, s = int(q[0]), int(q[1])
    if cnt + 1 > max_tx or s + amount_cents > max_sum:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Velocity limit")


def check_qr_velocity(db: Session, user, inc_tx: int):
    max_tx = _cfg_int("FRAUD_QR_MAX_TX_PER_HOUR", 200)
    since = datetime.utcnow() - timedelta(hours=1)
    w = db.query(Wallet).filter(Wallet.user_id == user.id).one()
    cnt = (
        db.query(func.count(Transfer.id))
        .filter(Transfer.from_wallet_id == w.id, Transfer.created_at >= since)
        .scalar()
        or 0
    )
    if cnt + inc_tx > max_tx:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Velocity limit")

