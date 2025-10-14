from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field

from ..auth import get_current_user, get_db
from ..models import Wallet, User, Transfer, LedgerEntry, Merchant, Refund
from ..schemas import TransferOut, RefundOut
from ..utils.audit import record_event
from ..models import WebhookEndpoint, WebhookDelivery
from . import webhooks as webhooks_router
from prometheus_client import Counter


REFUND_COUNTER = Counter("payments_refunds_total", "Refunds", ["status"]) 
REFUNDS_CENTS = Counter("payments_refunds_cents", "Refunded amount (cents)", ["currency"]) 

router = APIRouter(prefix="/refunds", tags=["refunds"]) 


class RefundCreateIn(BaseModel):
    original_transfer_id: str
    amount_cents: int = Field(gt=0)

@router.post("", response_model=TransferOut)
def create_refund(
    payload: RefundCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")
    # Original transfer
    t0 = db.execute(
        select(Transfer).where(Transfer.id == payload.original_transfer_id).with_for_update()
    ).scalar_one_or_none()
    if t0 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original transfer not found")
    # Determine merchant wallet (recipient of original)
    merchant_wallet = db.get(Wallet, t0.to_wallet_id)
    payer_wallet = db.get(Wallet, t0.from_wallet_id) if t0.from_wallet_id else None
    if merchant_wallet is None or payer_wallet is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid original transfer")
    # Ensure current user owns merchant wallet (merchant)
    if merchant_wallet.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not owner of original funds")

    # Idempotency check via Transfers table
    if idem_key:
        existing = db.query(Transfer).filter(Transfer.idempotency_key == idem_key).one_or_none()
        if existing:
            return TransferOut(
                transfer_id=str(existing.id),
                from_wallet_id=str(existing.from_wallet_id) if existing.from_wallet_id else None,
                to_wallet_id=str(existing.to_wallet_id),
                amount_cents=existing.amount_cents,
                currency_code=existing.currency_code,
                status=existing.status,
            )

    # Cap by refundable amount
    existing_refunds = db.execute(
        select(Refund.amount_cents)
        .where(Refund.original_transfer_id == t0.id, Refund.status == "completed")
        .with_for_update()
    ).scalars().all()
    already = sum(existing_refunds)
    remaining = max(0, t0.amount_cents - already)
    if payload.amount_cents > remaining:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exceeds refundable amount")

    # Lock wallets
    mw = db.query(Wallet).filter(Wallet.id == merchant_wallet.id).with_for_update().one()
    pw = db.query(Wallet).filter(Wallet.id == payer_wallet.id).with_for_update().one()
    if mw.currency_code != pw.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    if mw.balance_cents < payload.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    # Create refund transfer merchant -> payer
    t = Transfer(
        from_wallet_id=mw.id,
        to_wallet_id=pw.id,
        amount_cents=payload.amount_cents,
        currency_code=mw.currency_code,
        status="completed",
        idempotency_key=idem_key,
    )
    db.add(t)
    db.flush()

    db.add_all([
        LedgerEntry(transfer_id=t.id, wallet_id=mw.id, amount_cents_signed=-payload.amount_cents),
        LedgerEntry(transfer_id=t.id, wallet_id=pw.id, amount_cents_signed=payload.amount_cents),
    ])
    mw.balance_cents -= payload.amount_cents
    pw.balance_cents += payload.amount_cents

    # Record refund row
    r = Refund(
        original_transfer_id=t0.id,
        amount_cents=payload.amount_cents,
        currency_code=mw.currency_code,
        status="completed",
        idempotency_key=idem_key,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(r)
    db.flush()

    out = TransferOut(
        transfer_id=str(t.id),
        from_wallet_id=str(mw.id),
        to_wallet_id=str(pw.id),
        amount_cents=payload.amount_cents,
        currency_code=mw.currency_code,
        status=t.status,
    )
    record_event(db, "refunds.create", str(user.id), {"original": str(t0.id), "amount_cents": payload.amount_cents})
    try:
        REFUND_COUNTER.labels("completed").inc()
        REFUNDS_CENTS.labels(mw.currency_code).inc(payload.amount_cents)
    except Exception:
        pass
    # Enqueue webhook deliveries for merchant endpoints and attempt dispatch (best effort)
    try:
        payload_ev = {"type": "refunds.create", "data": {"original": str(t0.id), "amount_cents": payload.amount_cents}}
        eps = (
            db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.user_id == mw.user_id, WebhookEndpoint.active == True)
            .all()
        )
        any_created = False
        for e in eps:
            d = WebhookDelivery(endpoint_id=e.id, event_type=payload_ev["type"], payload=payload_ev, status="pending")
            db.add(d)
            any_created = True
        if any_created:
            db.flush()
            try:
                webhooks_router._process_once(db, limit=20)  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        pass
    return out


@router.get("/{refund_id}", response_model=RefundOut)
def get_refund(refund_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(Refund, refund_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # visibility: owner of original transfer's to_wallet
    t0 = db.get(Transfer, r.original_transfer_id)
    mw = db.get(Wallet, t0.to_wallet_id) if t0 else None
    if not t0 or not mw or mw.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return RefundOut(
        id=str(r.id),
        original_transfer_id=str(r.original_transfer_id),
        amount_cents=r.amount_cents,
        currency_code=r.currency_code,
        status=r.status,
        created_at=r.created_at.isoformat() + "Z",
    )
