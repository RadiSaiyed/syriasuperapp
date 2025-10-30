from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Wallet, PaymentRequest, Transfer, LedgerEntry
from ..schemas import CreateRequestIn, RequestOut, RequestsListOut
from ..utils.kyc_policy import enforce_tx_limits
from ..utils.audit import record_event
from ..models import WebhookEndpoint, WebhookDelivery
from . import webhooks as webhooks_router
from prometheus_client import Counter
from ..config import settings

REQ_COUNTER = Counter("payments_requests_total", "Payment requests", ["action"]) 


router = APIRouter(prefix="/requests", tags=["requests"])


def _to_request_out(db: Session, r: PaymentRequest) -> RequestOut:
    requester = db.get(User, r.requester_user_id)
    target = db.get(User, r.target_user_id)
    return RequestOut(
        id=str(r.id),
        requester_phone=requester.phone if requester else "",
        target_phone=target.phone if target else "",
        amount_cents=r.amount_cents,
        currency_code=r.currency_code,
        status=r.status,
        created_at=r.created_at.isoformat() + "Z",
        expires_at=(r.expires_at.isoformat() + "Z") if r.expires_at else None,
        metadata=r.metadata_json or None,
    )


@router.post("", response_model=RequestOut)
def create_request(
    payload: CreateRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idem_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid amount")
    target = db.query(User).filter(User.phone == payload.to_phone).one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    if target.id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot request from self")

    # If idempotency key is provided, return existing
    if idem_key:
        existing = db.query(PaymentRequest).filter(PaymentRequest.idempotency_key == idem_key).one_or_none()
        if existing is not None:
            return _to_request_out(db, existing)

    # expiry
    exp: datetime | None = None
    if payload.expires_in_minutes is not None:
        exp = datetime.utcnow() + timedelta(minutes=payload.expires_in_minutes)
    elif settings.REQUEST_EXPIRY_MINUTES:
        exp = datetime.utcnow() + timedelta(minutes=settings.REQUEST_EXPIRY_MINUTES)

    pr = PaymentRequest(
        requester_user_id=user.id,
        target_user_id=target.id,
        amount_cents=payload.amount_cents,
        currency_code=settings.DEFAULT_CURRENCY,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        expires_at=exp,
        metadata_json=payload.metadata,
        idempotency_key=idem_key,
    )
    db.add(pr)
    db.flush()
    out = _to_request_out(db, pr)
    record_event(db, "requests.create", str(user.id), {"to": payload.to_phone, "amount_cents": payload.amount_cents})
    try:
        REQ_COUNTER.labels("create").inc()
    except Exception:
        pass
    return out


@router.get("", response_model=RequestsListOut)
def list_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    incoming = db.query(PaymentRequest).filter(PaymentRequest.target_user_id == user.id).order_by(PaymentRequest.created_at.desc()).limit(100).all()
    outgoing = db.query(PaymentRequest).filter(PaymentRequest.requester_user_id == user.id).order_by(PaymentRequest.created_at.desc()).limit(100).all()
    out = RequestsListOut(
        incoming=[_to_request_out(db, r) for r in incoming],
        outgoing=[_to_request_out(db, r) for r in outgoing],
    )
    return out


@router.get("/{request_id}", response_model=RequestOut)
def get_request_detail(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    # Visibility: requester or target can view
    if pr.requester_user_id != user.id and pr.target_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # Auto-expire
    if pr.status == "pending" and pr.expires_at and datetime.utcnow() > pr.expires_at:
        pr.status = "expired"
        pr.updated_at = datetime.utcnow()
        db.flush()
    out = _to_request_out(db, pr)
    record_event(db, "requests.get", str(user.id), {"id": request_id})
    return out


@router.post("/{request_id}/accept")
def accept_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if pr.target_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your request to accept")
    # Expired?
    if pr.status == "pending" and pr.expires_at and datetime.utcnow() > pr.expires_at:
        pr.status = "expired"
        pr.updated_at = datetime.utcnow()
        db.flush()
    if pr.status != "pending":
        return {"detail": f"already {pr.status}"}

    payer_wallet = db.query(Wallet).filter(Wallet.user_id == pr.target_user_id).with_for_update().one()
    receiver_wallet = db.query(Wallet).filter(Wallet.user_id == pr.requester_user_id).with_for_update().one()
    if payer_wallet.currency_code != receiver_wallet.currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency mismatch")
    # KYC limits for payer
    enforce_tx_limits(db, user, pr.amount_cents)
    if payer_wallet.balance_cents < pr.amount_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    t = Transfer(
        from_wallet_id=payer_wallet.id,
        to_wallet_id=receiver_wallet.id,
        amount_cents=pr.amount_cents,
        currency_code=payer_wallet.currency_code,
        status="completed",
        idempotency_key=None,
    )
    db.add(t)
    db.flush()

    db.add_all(
        [
            LedgerEntry(transfer_id=t.id, wallet_id=payer_wallet.id, amount_cents_signed=-pr.amount_cents),
            LedgerEntry(transfer_id=t.id, wallet_id=receiver_wallet.id, amount_cents_signed=pr.amount_cents),
        ]
    )
    payer_wallet.balance_cents -= pr.amount_cents
    receiver_wallet.balance_cents += pr.amount_cents

    pr.status = "accepted"
    pr.updated_at = datetime.utcnow()
    db.flush()
    record_event(db, "requests.accept", str(user.id), {"id": request_id, "transfer_id": str(t.id)})
    try:
        REQ_COUNTER.labels("accept").inc()
    except Exception:
        pass
    # Enqueue webhook deliveries for requester (merchant) endpoints and attempt dispatch (best effort)
    try:
        payload = {"type": "requests.accept", "data": {"id": request_id, "transfer_id": str(t.id)}}
        eps = (
            db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.user_id == pr.requester_user_id, WebhookEndpoint.active == True)
            .all()
        )
        any_created = False
        for e in eps:
            d = WebhookDelivery(endpoint_id=e.id, event_type=payload["type"], payload=payload, status="pending")
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
    return {"detail": "accepted", "transfer_id": str(t.id)}


@router.post("/{request_id}/reject")
def reject_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if pr.target_user_id != user.id and pr.requester_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if pr.status != "pending":
        return {"detail": f"already {pr.status}"}
    pr.status = "rejected"
    pr.updated_at = datetime.utcnow()
    db.flush()
    record_event(db, "requests.reject", str(user.id), {"id": request_id})
    try:
        REQ_COUNTER.labels("reject").inc()
    except Exception:
        pass
    return {"detail": "rejected"}


@router.post("/{request_id}/cancel")
def cancel_request(request_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if pr.requester_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only requester can cancel")
    if pr.status != "pending":
        return {"detail": f"already {pr.status}"}
    pr.status = "canceled"
    pr.updated_at = datetime.utcnow()
    db.flush()
    record_event(db, "requests.cancel", str(user.id), {"id": request_id})
    try:
        REQ_COUNTER.labels("cancel").inc()
    except Exception:
        pass
    return {"detail": "canceled"}
