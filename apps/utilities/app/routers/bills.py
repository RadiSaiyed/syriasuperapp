from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import httpx

from ..auth import get_current_user, get_db
from ..config import settings
from ..models import User, Biller, BillerAccount, Bill
from ..schemas import BillOut, BillsListOut
import os
import httpx


router = APIRouter(prefix="/bills", tags=["bills"])


def _to_bill_out(b: Bill) -> BillOut:
    return BillOut(
        id=str(b.id), biller_id=str(b.biller_id), account_id=str(b.account_id), amount_cents=b.amount_cents, status=b.status, due_date=b.due_date, payment_request_id=b.payment_request_id
    )


@router.post("/refresh", response_model=BillsListOut)
def refresh_bills(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acc = db.get(BillerAccount, account_id)
    if acc is None or acc.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    # DEV: seed pending bills if none exist
    existing = db.query(Bill).filter(Bill.account_id == acc.id, Bill.status == "pending").all()
    if not existing:
        due = date.today() + timedelta(days=7)
        for i in range(1, 3):
            db.add(Bill(user_id=user.id, biller_id=acc.biller_id, account_id=acc.id, amount_cents=5000 * i, status="pending", due_date=due))
        db.flush()
    rows = db.query(Bill).filter(Bill.account_id == acc.id).order_by(Bill.created_at.desc()).all()
    return BillsListOut(bills=[_to_bill_out(b) for b in rows])


@router.get("", response_model=BillsListOut)
def list_bills(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Bill).filter(Bill.user_id == user.id).order_by(Bill.created_at.desc()).limit(100).all()
    return BillsListOut(bills=[_to_bill_out(b) for b in rows])


@router.post("/{bill_id}/pay", response_model=BillOut)
def pay_bill(bill_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bill = db.get(Bill, bill_id)
    if bill is None or bill.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    if bill.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    payment_request_id = None
    try:
        if settings.PAYMENTS_BASE_URL and settings.PAYMENTS_INTERNAL_SECRET and bill.amount_cents > 0:
            # Create an Invoice in Payments (issuer = configured aggregator), payer = current user
            from_phone = settings.PAYMENTS_EBILL_ISSUER_PHONE
            # Due days from due_date if present
            due_in_days = 0
            if bill.due_date and isinstance(bill.due_date, date):
                due_in_days = max(0, (bill.due_date - date.today()).days)
            # Build reference/description best-effort
            biller = db.get(Biller, bill.biller_id)
            acc = db.get(BillerAccount, bill.account_id)
            reference = f"{biller.name if biller else 'Bill'}-{acc.account_ref if acc else ''}"
            desc = f"Utilities bill {biller.name if biller else ''} for {acc.account_ref if acc else ''}"
            # Membership discount (MVP): apply 10% off if member benefit present
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
                # Use stable idempotency per bill
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
