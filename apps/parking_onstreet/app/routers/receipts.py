from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..auth import get_current_user, get_db
from ..models import Receipt, Session as ParkSession


router = APIRouter(prefix="/receipts", tags=["receipts"])


class ReceiptRes(BaseModel):
    id: str
    session_id: str
    minutes: int
    gross_cents: int
    fee_cents: int
    net_cents: int
    currency: str


@router.get("/{session_id}", response_model=ReceiptRes)
def get_receipt(session_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "session_not_found")
    r = db.query(Receipt).filter(Receipt.session_id == s.id).one_or_none()
    if not r:
        raise HTTPException(404, "receipt_not_found")
    return ReceiptRes(
        id=str(r.id),
        session_id=str(r.session_id),
        minutes=r.minutes,
        gross_cents=r.gross_cents,
        fee_cents=r.fee_cents,
        net_cents=r.net_cents,
        currency=r.currency,
    )

