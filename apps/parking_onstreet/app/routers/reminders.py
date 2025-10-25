from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..auth import get_current_user, get_db
from ..models import Reminder, Session as ParkSession


router = APIRouter(prefix="/reminders", tags=["reminders"])


class CreateReq(BaseModel):
    session_id: str
    minutes_before: int = 10
    type: str = "expiry"


class ReminderRes(BaseModel):
    id: str
    session_id: str
    at: datetime
    type: str
    minutes_before: int | None


@router.post("/", response_model=ReminderRes)
def create(req: CreateReq, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, req.session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "session_not_found")
    # schedule at (start + assumed end - minutes_before). For MVP assume 1h windows if running.
    base_at = datetime.utcnow() + timedelta(minutes=60)
    at = base_at - timedelta(minutes=req.minutes_before)
    r = Reminder(session_id=s.id, at=at, type=req.type, minutes_before=req.minutes_before)
    db.add(r)
    db.flush()
    return ReminderRes(id=str(r.id), session_id=str(s.id), at=r.at, type=r.type, minutes_before=r.minutes_before)


@router.get("/{session_id}", response_model=list[ReminderRes])
def list_for_session(session_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(ParkSession, session_id)
    if not s or s.user_id != user.id:
        raise HTTPException(404, "session_not_found")
    rows = db.query(Reminder).filter(Reminder.session_id == s.id).order_by(Reminder.at.asc()).all()
    return [ReminderRes(id=str(x.id), session_id=str(x.session_id), at=x.at, type=x.type, minutes_before=x.minutes_before) for x in rows]

