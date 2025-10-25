import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import User, Driver, TaxiWallet, TaxiWalletEntry
from sqlalchemy import func
import uuid as _uuid
import httpx
from ..payments_cb import allowed as pay_allowed, record as pay_record
from prometheus_client import Counter


router = APIRouter(prefix="/driver/taxi_wallet", tags=["taxi_wallet"])
logger = logging.getLogger("taxi.wallet")

WALLET_EVENTS = Counter(
    "taxi_wallet_events_total",
    "Taxi wallet operations",
    ["operation", "result"],
)


def _require_driver(user: User):
    if user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver only")


def _get_or_create_wallet(db: Session, driver: Driver) -> TaxiWallet:
    w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == driver.id).one_or_none()
    if w is None:
        w = TaxiWallet(driver_id=driver.id, balance_cents=0)
        db.add(w)
        db.flush()
    return w


@router.get("")
def get_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_driver(user)
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    w = _get_or_create_wallet(db, drv)
    # recent entries
    q = (
        db.query(TaxiWalletEntry)
        .filter(TaxiWalletEntry.wallet_id == w.id)
        .order_by(TaxiWalletEntry.created_at.desc())
        .limit(50)
        .all()
    )
    items = []
    for e in q:
        items.append(
            {
                "id": str(e.id),
                "type": e.type,
                "amount_cents_signed": e.amount_cents_signed,
                "ride_id": str(e.ride_id) if e.ride_id else None,
                "original_fare_cents": e.original_fare_cents,
                "fee_cents": e.fee_cents,
                "driver_take_home_cents": e.driver_take_home_cents,
                "created_at": e.created_at.isoformat() + "Z",
            }
        )
    return {
        "balance_cents": w.balance_cents,
        "entries": items,
        "linked_main_wallet_phone": user.phone,
    }


@router.post("/topup")
def topup_wallet(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_driver(user)
    amount_cents = int(payload.get("amount_cents") or 0)
    if amount_cents <= 0:
        WALLET_EVENTS.labels("topup", "invalid").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_amount")
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    w = _get_or_create_wallet(db, drv)

    # Move funds from main wallet -> taxi pool (payments), if configured
    if settings.TAXI_POOL_WALLET_PHONE and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("wallet_topup"):
        body = {"from_phone": user.phone, "to_phone": settings.TAXI_POOL_WALLET_PHONE, "amount_cents": amount_cents}
        try:
            from superapp_shared.internal_hmac import sign_internal_request_headers
            idem = f"taxi:topup:{w.id}:{_uuid.uuid4()}"
            headers = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            headers["X-Idempotency-Key"] = idem
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers)
                if r.status_code >= 400:
                    pay_record("wallet_topup", False)
                    WALLET_EVENTS.labels("topup", "payments_error").inc()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="topup_failed")
                pay_record("wallet_topup", True)
        except HTTPException:
            raise
        except Exception:
            pay_record("wallet_topup", False)
            WALLET_EVENTS.labels("topup", "payments_error").inc()
            logger.exception("Payments topup transfer failed")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_error")

    # Credit taxi wallet
    w.balance_cents += amount_cents
    db.add(
        TaxiWalletEntry(
            wallet_id=w.id,
            type="topup",
            amount_cents_signed=amount_cents,
        )
    )
    db.flush()
    WALLET_EVENTS.labels("topup", "success").inc()
    return {"detail": "ok", "balance_cents": w.balance_cents}


@router.post("/withdraw")
def withdraw_wallet(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_driver(user)
    amount_cents = int(payload.get("amount_cents") or 0)
    if amount_cents <= 0:
        WALLET_EVENTS.labels("withdraw", "invalid").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_amount")
    drv = db.query(Driver).filter(Driver.user_id == user.id).one()
    w = _get_or_create_wallet(db, drv)
    if w.balance_cents < amount_cents:
        WALLET_EVENTS.labels("withdraw", "insufficient").inc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="insufficient_funds")

    # Move funds from taxi pool -> main wallet (payments), if configured
    if settings.TAXI_POOL_WALLET_PHONE and settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and pay_allowed("wallet_withdraw"):
        body = {"from_phone": settings.TAXI_POOL_WALLET_PHONE, "to_phone": user.phone, "amount_cents": amount_cents}
        try:
            from superapp_shared.internal_hmac import sign_internal_request_headers
            idem = f"taxi:withdraw:{w.id}:{_uuid.uuid4()}"
            headers = sign_internal_request_headers(body, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            headers["X-Idempotency-Key"] = idem
            with httpx.Client(timeout=5.0) as client:
                r = client.post(f"{settings.PAYMENTS_BASE_URL}/internal/transfer", json=body, headers=headers)
                if r.status_code >= 400:
                    pay_record("wallet_withdraw", False)
                    WALLET_EVENTS.labels("withdraw", "payments_error").inc()
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="withdraw_failed")
                pay_record("wallet_withdraw", True)
        except HTTPException:
            raise
        except Exception:
            pay_record("wallet_withdraw", False)
            WALLET_EVENTS.labels("withdraw", "payments_error").inc()
            logger.exception("Payments withdraw transfer failed")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="payments_error")

    # Debit taxi wallet
    w.balance_cents -= amount_cents
    db.add(
        TaxiWalletEntry(
            wallet_id=w.id,
            type="withdraw",
            amount_cents_signed=-amount_cents,
        )
    )
    db.flush()
    WALLET_EVENTS.labels("withdraw", "success").inc()
    return {"detail": "ok", "balance_cents": w.balance_cents}
