import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import Wallet, User, Transfer, LedgerEntry, Merchant, PaymentLink
from ..schemas import TransferOut
from ..utils.kyc_policy import require_min_kyc_level, enforce_tx_limits
from ..utils.fees import ensure_fee_wallet, calc_fee_bps
from ..utils.audit import record_event
from prometheus_client import Counter
from ..utils.risk import evaluate_risk_and_maybe_block


LINK_COUNTER = Counter("payments_links_total", "Pay-by-link payments", ["action"]) 

router = APIRouter(prefix="/payments/links", tags=["links"]) 


from pydantic import BaseModel, Field


class LinkCreateIn(BaseModel):
    amount_cents: int | None = Field(default=None, gt=0)
    currency_code: str = "SYP"
    expires_in_minutes: int | None = Field(default=None, ge=1, le=7*24*60)


@router.post("", response_model=dict)
def create_link(payload: LinkCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_min_kyc_level(user, settings.KYC_MIN_LEVEL_FOR_MERCHANT_QR)
    # Ensure merchant exists
    merchant = db.query(Merchant).filter(Merchant.user_id == user.id).one_or_none()
    if merchant is None:
        wallet = db.query(Wallet).filter(Wallet.user_id == user.id).one()
        merchant = Merchant(user_id=user.id, wallet_id=wallet.id)
        db.add(merchant)
        db.flush()

    mode = "dynamic" if (payload.amount_cents and payload.amount_cents > 0) else "static"
    expires_at = None
    if payload.expires_in_minutes:
        expires_at = datetime.utcnow() + timedelta(minutes=payload.expires_in_minutes)

    code = secrets.token_urlsafe(24)
    link = PaymentLink(
        user_id=user.id,
        code=code,
        amount_cents=payload.amount_cents or 0,
        currency_code=payload.currency_code,
        mode=mode,
        status="active",
        expires_at=expires_at,
    )
    db.add(link)
    db.flush()
    try:
        LINK_COUNTER.labels("create").inc()
    except Exception:
        pass
    return {"code": f"LINK:v1;code={code}", "expires_at": (expires_at.isoformat()+"Z") if expires_at else None}


class LinkPayIn(BaseModel):
    code: str
    idempotency_key: str
    amount_cents: int | None = Field(default=None, gt=0)


@router.post("/pay", response_model=TransferOut)
def pay_link(
    payload: LinkPayIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # KYC
    require_min_kyc_level(user, settings.KYC_MIN_LEVEL_FOR_MERCHANT_PAY)

    prefix = "LINK:v1;code="
    if not payload.code.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid link format")
    opaque = payload.code[len(prefix):]

    link = db.query(PaymentLink).filter(PaymentLink.code == opaque).with_for_update().one_or_none()
    if link is None or link.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not active")
    if link.expires_at and link.expires_at < datetime.utcnow():
        link.status = "expired"
        db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link expired")

    # Determine amount
    amount = link.amount_cents
    if link.mode == "static":
        if payload.amount_cents is None or payload.amount_cents <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount required for static link")
        amount = payload.amount_cents
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")

    # Idempotency via transfers
    existing = db.query(Transfer).filter(Transfer.idempotency_key == payload.idempotency_key).one_or_none()
    if existing:
        return TransferOut(
            transfer_id=str(existing.id),
            from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
            to_wallet_id=str(existing.to_wallet_id),
            amount_cents=existing.amount_cents,
            currency_code=existing.currency_code,
            status=existing.status,
        )

    payer_wallet = db.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().one()
    merchant_wallet = db.query(Wallet).join(User, Wallet.user_id == User.id).filter(User.id == link.user_id).with_for_update().one()
    if payer_wallet.currency_code != link.currency_code or merchant_wallet.currency_code != link.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    enforce_tx_limits(db, user, amount)
    # Risk engine (optional)
    try:
        evaluate_risk_and_maybe_block(db, user, amount, context="link_pay", merchant_user_id=str(merchant_wallet.user_id))
    except Exception:
        # allow HTTPException to bubble naturally
        from fastapi import HTTPException as _HE
        import sys
        e = sys.exc_info()[1]
        if isinstance(e, _HE):
            raise
        pass
    if payer_wallet.balance_cents < amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    t = Transfer(
        from_wallet_id=payer_wallet.id,
        to_wallet_id=merchant_wallet.id,
        amount_cents=amount,
        currency_code=link.currency_code,
        status="completed",
        idempotency_key=payload.idempotency_key,
    )
    db.add(t); db.flush()
    db.add_all([
        LedgerEntry(transfer_id=t.id, wallet_id=payer_wallet.id, amount_cents_signed=-amount),
        LedgerEntry(transfer_id=t.id, wallet_id=merchant_wallet.id, amount_cents_signed=amount),
    ])
    payer_wallet.balance_cents -= amount
    merchant_wallet.balance_cents += amount
    # One-time links are marked used
    if link.mode == "dynamic":
        link.status = "used"
    db.flush()

    # Fee
    from ..utils.fees import calc_fee_bps, ensure_fee_wallet
    fee_bps = settings.MERCHANT_FEE_BPS
    fee_amount = calc_fee_bps(amount, fee_bps)
    if fee_amount > 0:
        fee_wallet = ensure_fee_wallet(db)
        if merchant_wallet.balance_cents < fee_amount:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Fee settlement failed")
        tf = Transfer(
            from_wallet_id=merchant_wallet.id,
            to_wallet_id=fee_wallet.id,
            amount_cents=fee_amount,
            currency_code=link.currency_code,
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

    out = TransferOut(
        transfer_id=str(t.id),
        from_wallet_id=str(payer_wallet.id),
        to_wallet_id=str(merchant_wallet.id),
        amount_cents=amount,
        currency_code=link.currency_code,
        status=t.status,
    )
    record_event(db, "links.pay", str(user.id), {"amount_cents": amount})
    try:
        LINK_COUNTER.labels("pay").inc()
    except Exception:
        pass
    return out
