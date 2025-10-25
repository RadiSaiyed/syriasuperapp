from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import User, Wallet, Merchant, Subscription, Transfer, LedgerEntry
from ..utils.kyc_policy import enforce_tx_limits, require_min_kyc_level
from ..utils.fees import ensure_fee_wallet, calc_fee_bps
from ..utils.audit import record_event
from prometheus_client import Counter
from ..utils.risk import evaluate_risk_and_maybe_block
from pydantic import BaseModel, Field


SUB_COUNTER = Counter("payments_subscriptions_total", "Subscriptions", ["action"]) 
SUB_CENTS = Counter("payments_subscriptions_cents", "Subscription charges (cents)", ["currency"]) 

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"]) 


class CreateSubscriptionIn(BaseModel):
    merchant_phone: str
    amount_cents: int = Field(gt=0)
    interval_days: int = Field(default=30, ge=1, le=365)


@router.post("", response_model=dict)
def create_subscription(payload: CreateSubscriptionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")
    if payload.interval_days < 1 or payload.interval_days > 365:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid interval")
    # Merchant lookup
    merchant_user = db.query(User).filter(User.phone == payload.merchant_phone).one_or_none()
    if merchant_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found")
    if not merchant_user.is_merchant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target is not a merchant")
    # Enforce KYC min for payer
    enforce_tx_limits(db, user, payload.amount_cents)  # baseline check at creation time

    next_charge = datetime.utcnow() + timedelta(days=payload.interval_days)
    sub = Subscription(
        payer_user_id=user.id,
        merchant_user_id=merchant_user.id,
        amount_cents=payload.amount_cents,
        currency_code="SYP",
        interval_days=payload.interval_days,
        next_charge_at=next_charge,
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(sub)
    db.flush()
    try:
        SUB_COUNTER.labels("created").inc()
    except Exception:
        pass
    return {"id": str(sub.id), "next_charge_at": next_charge.isoformat() + "Z"}


@router.get("")
def list_subscriptions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Subscription)
        .filter(Subscription.payer_user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": str(s.id),
            "merchant_user_id": str(s.merchant_user_id),
            "amount_cents": s.amount_cents,
            "currency_code": s.currency_code,
            "interval_days": s.interval_days,
            "next_charge_at": s.next_charge_at.isoformat() + "Z",
            "status": s.status,
            "created_at": s.created_at.isoformat() + "Z",
        }
        for s in rows
    ]


@router.post("/{sub_id}/cancel")
def cancel_subscription(sub_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Subscription, sub_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if s.payer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if s.status != "active":
        return {"detail": f"already {s.status}"}
    s.status = "canceled"
    s.updated_at = datetime.utcnow()
    db.flush()
    try:
        SUB_COUNTER.labels("canceled").inc()
    except Exception:
        pass
    return {"detail": "canceled"}


def _charge_subscription(db: Session, s: Subscription) -> bool:
    # Lock wallets
    payer_wallet = db.query(Wallet).filter(Wallet.user_id == s.payer_user_id).with_for_update().one()
    merchant_wallet = db.query(Wallet).filter(Wallet.user_id == s.merchant_user_id).with_for_update().one()
    if payer_wallet.currency_code != s.currency_code or merchant_wallet.currency_code != s.currency_code:
        return False
    # Enforce limits
    payer = db.get(User, s.payer_user_id)
    enforce_tx_limits(db, payer, s.amount_cents)
    try:
        evaluate_risk_and_maybe_block(db, payer, s.amount_cents, context="subscription_charge", merchant_user_id=str(s.merchant_user_id))
    except HTTPException:
        return False
    if payer_wallet.balance_cents < s.amount_cents:
        return False
    # Transfer
    t = Transfer(
        from_wallet_id=payer_wallet.id,
        to_wallet_id=merchant_wallet.id,
        amount_cents=s.amount_cents,
        currency_code=s.currency_code,
        status="completed",
        idempotency_key=None,
    )
    db.add(t); db.flush()
    db.add_all([
        LedgerEntry(transfer_id=t.id, wallet_id=payer_wallet.id, amount_cents_signed=-s.amount_cents),
        LedgerEntry(transfer_id=t.id, wallet_id=merchant_wallet.id, amount_cents_signed=s.amount_cents),
    ])
    payer_wallet.balance_cents -= s.amount_cents
    merchant_wallet.balance_cents += s.amount_cents
    db.flush()
    # Fee
    fee_amount = calc_fee_bps(s.amount_cents, settings.MERCHANT_FEE_BPS)
    if fee_amount > 0:
        fee_wallet = ensure_fee_wallet(db)
        if merchant_wallet.balance_cents >= fee_amount:
            tf = Transfer(
                from_wallet_id=merchant_wallet.id,
                to_wallet_id=fee_wallet.id,
                amount_cents=fee_amount,
                currency_code=s.currency_code,
                status="completed",
                idempotency_key=None,
            )
            db.add(tf); db.flush()
            db.add_all([
                LedgerEntry(transfer_id=tf.id, wallet_id=merchant_wallet.id, amount_cents_signed=-fee_amount),
                LedgerEntry(transfer_id=tf.id, wallet_id=fee_wallet.id, amount_cents_signed=fee_amount),
            ])
            merchant_wallet.balance_cents -= fee_amount
            fee_wallet.balance_cents += fee_amount
            db.flush()

    try:
        SUB_COUNTER.labels("charged").inc()
        SUB_CENTS.labels(s.currency_code).inc(s.amount_cents)
    except Exception:
        pass
    return True


@router.post("/process_due")
def process_due(user: User = Depends(get_current_user), db: Session = Depends(get_db), max_count: int = 50):
    # Dev‑only processing helper
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    now = datetime.utcnow()
    due = (
        db.query(Subscription)
        .filter(Subscription.status == "active", Subscription.next_charge_at <= now)
        .order_by(Subscription.next_charge_at.asc())
        .limit(max_count)
        .all()
    )
    processed = 0
    for s in due:
        ok = False
        try:
            ok = _charge_subscription(db, s)
        except Exception:
            ok = False
        # schedule next
        s.next_charge_at = now + timedelta(days=s.interval_days)
        s.updated_at = datetime.utcnow()
        db.flush()
        if ok:
            processed += 1
    return {"processed": processed, "count": len(due)}


@router.post("/{sub_id}/dev_force_due")
def dev_force_due(sub_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Dev helper: force next_charge_at to now for a specific subscription
    if settings.ENV != "dev":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    s = db.get(Subscription, sub_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if s.payer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    s.next_charge_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    db.flush()
    return {"detail": "ok"}
