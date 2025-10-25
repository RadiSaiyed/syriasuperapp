from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import date
import os
import httpx

from ..auth import get_current_user, get_db
from ..models import User, BillerAccount, AutoPayRule, Bill


router = APIRouter(prefix="/autopay", tags=["autopay"])


class AutoPayIn(BaseModel):
    account_id: str
    day_of_month: int | None = Field(default=None, ge=1, le=28, description="1..28 or None to use bill due_date")
    max_amount_cents: int | None = Field(default=None, ge=0)
    enabled: bool = True


class AutoPayOut(BaseModel):
    id: str
    account_id: str
    day_of_month: int | None
    max_amount_cents: int | None
    enabled: bool


@router.post("/rules", response_model=AutoPayOut)
def upsert_rule(payload: AutoPayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acc = db.get(BillerAccount, payload.account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    rule = db.query(AutoPayRule).filter(AutoPayRule.user_id == user.id, AutoPayRule.account_id == acc.id).one_or_none()
    if rule is None:
        rule = AutoPayRule(user_id=user.id, account_id=acc.id)
        db.add(rule)
    rule.day_of_month = payload.day_of_month
    rule.max_amount_cents = payload.max_amount_cents
    rule.enabled = bool(payload.enabled)
    db.flush()
    return AutoPayOut(id=str(rule.id), account_id=str(rule.account_id), day_of_month=rule.day_of_month, max_amount_cents=rule.max_amount_cents, enabled=rule.enabled)


@router.get("/rules", response_model=list[AutoPayOut])
def list_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(AutoPayRule).filter(AutoPayRule.user_id == user.id).all()
    return [AutoPayOut(id=str(r.id), account_id=str(r.account_id), day_of_month=r.day_of_month, max_amount_cents=r.max_amount_cents, enabled=r.enabled) for r in rows]


@router.post("/run")
def run_now(user: User = Depends(get_current_user), db: Session = Depends(get_db), authorization: str | None = Header(default=None, alias="Authorization")):
    # For each enabled rule, if today matches (or bill is due today) and amount <= cap, trigger internal pay.
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    rules = db.query(AutoPayRule).filter(AutoPayRule.user_id == user.id, AutoPayRule.enabled == True).all()  # noqa: E712
    ran = 0
    for r in rules:
        bills = db.query(Bill).filter(Bill.account_id == r.account_id, Bill.status == "pending").all()
        for b in bills:
            today = date.today()
            match = False
            if r.day_of_month:
                match = today.day == r.day_of_month
            else:
                match = (b.due_date == today)
            if not match:
                continue
            if r.max_amount_cents is not None and b.amount_cents > r.max_amount_cents:
                continue
            # Trigger local bill pay endpoint with the user's Authorization
            try:
                with httpx.Client(timeout=5.0) as client:
                    r = client.post("http://localhost:8084/bills/%s/pay" % str(b.id), headers={"Authorization": authorization or ""})
                    if r.status_code < 400:
                        ran += 1
            except Exception:
                pass
    return {"detail": "ok", "triggered": ran}
