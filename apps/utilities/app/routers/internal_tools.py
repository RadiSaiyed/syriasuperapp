from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import httpx
from pydantic import BaseModel

from ..auth import get_current_user, get_db
from ..models import User, Biller, BillerAccount, Bill
from ..schemas import BillOut
from ..config import settings
from superapp_shared.internal_hmac import verify_internal_hmac_with_replay
import os
import httpx


router = APIRouter(prefix="/internal/tools", tags=["internal_tools"])  # internal, HMAC protected


class PayBillIn(BaseModel):
    user_id: str
    bill_id: str


def _to_bill_out(b: Bill) -> BillOut:
    return BillOut(
        id=str(b.id), biller_id=str(b.biller_id), account_id=str(b.account_id), amount_cents=b.amount_cents, status=b.status, due_date=b.due_date, payment_request_id=b.payment_request_id
    )


@router.post("/pay_bill", response_model=BillOut)
def pay_bill_internal(payload: PayBillIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Verify HMAC to ensure caller is allowed (AI Gateway) and prevent replay
    ts = request.headers.get("X-Internal-Ts") or ""
    sign = request.headers.get("X-Internal-Sign") or ""
    ok = verify_internal_hmac_with_replay(ts, payload.model_dump(), sign, settings.INTERNAL_API_SECRET, redis_url=settings.REDIS_URL, ttl_secs=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Ensure token user matches target user
    if str(user.id) != str(payload.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user mismatch")

    bill = db.get(Bill, payload.bill_id)
    if bill is None or str(bill.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    if bill.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    # Create payments invoice if configured
    payment_request_id = None
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and bill.amount_cents > 0:
            from_phone = settings.PAYMENTS_EBILL_ISSUER_PHONE
            due_in_days = 0
            if bill.due_date and isinstance(bill.due_date, date):
                from datetime import date as _d
                due_in_days = max(0, (bill.due_date - _d.today()).days)
            biller = db.get(Biller, bill.biller_id)
            acc = db.get(BillerAccount, bill.account_id)
            reference = f"{biller.name if biller else 'Bill'}-{acc.account_ref if acc else ''}"
            desc = f"Utilities bill {biller.name if biller else ''} for {acc.account_ref if acc else ''}"
            # Membership discount (MVP): 10% if member benefit present
            amount_cents = bill.amount_cents
            try:
                base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
                with httpx.Client(base_url=base, timeout=3.0) as client:
                    r = client.get("/v1/membership/status", params={"user_id": str(user.id), "phone": user.phone})
                    if r.status_code < 400:
                        bens = (r.json() or {}).get("benefits", []) or []
                        if any(b.startswith("fee_discount_") for b in bens):
                            perc = 10
                            for b in bens:
                                if b.startswith("fee_discount_"):
                                    try:
                                        perc = int(b.split("_")[-1])
                                    except Exception:
                                        pass
                            amount_cents = int(round(amount_cents * (1 - perc / 100.0)))
            except Exception:
                pass
            payload_json = {
                "from_phone": from_phone,
                "to_phone": user.phone,
                "amount_cents": max(0, amount_cents),
                "due_in_days": due_in_days,
                "reference": reference[:128],
                "description": desc[:512],
            }
            from superapp_shared.internal_hmac import sign_internal_request_headers
            headers = sign_internal_request_headers(payload_json, settings.PAYMENTS_INTERNAL_SECRET, request.headers.get("X-Request-ID", ""))
            with httpx.Client(timeout=5.0) as client:
                headers_extra = {"X-Idempotency-Key": f"util-bill-{bill.id}"}
                r = client.post(
                    f"{settings.PAYMENTS_BASE_URL}/internal/invoices",
                    headers={**headers, **headers_extra},
                    json=payload_json,
                )
                if r.status_code < 400:
                    payment_request_id = r.json().get("id")
    except Exception:
        pass

    if payment_request_id:
        bill.payment_request_id = payment_request_id
    db.flush()
    return _to_bill_out(bill)
