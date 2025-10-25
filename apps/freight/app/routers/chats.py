from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Load, LoadChatMessage, CarrierProfile
from ..schemas import ChatIn, ChatMessageOut, ChatListOut


router = APIRouter(prefix="/chats", tags=["chats"]) 


def _can_chat(db: Session, user: User, load: Load) -> bool:
    if load.shipper_user_id == user.id:
        return True
    if load.carrier_id:
        carrier = db.query(CarrierProfile).filter(CarrierProfile.id == load.carrier_id).one_or_none()
        if carrier and carrier.user_id == user.id:
            return True
    return False


@router.get("/load/{load_id}", response_model=ChatListOut)
def list_messages(load_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Load, load_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Load not found")
    if not _can_chat(db, user, l):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(LoadChatMessage).filter(LoadChatMessage.load_id == l.id).order_by(LoadChatMessage.created_at.asc()).limit(200).all()
    return ChatListOut(messages=[ChatMessageOut(id=str(m.id), load_id=str(m.load_id), from_user_id=str(m.from_user_id), content=m.content, created_at=m.created_at) for m in rows])


@router.post("/load/{load_id}", response_model=ChatMessageOut)
def post_message(load_id: str, payload: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Load, load_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Load not found")
    if not _can_chat(db, user, l):
        raise HTTPException(status_code=403, detail="Forbidden")
    m = LoadChatMessage(load_id=l.id, from_user_id=user.id, content=payload.content.strip())
    db.add(m)
    db.flush()
    return ChatMessageOut(id=str(m.id), load_id=str(m.load_id), from_user_id=str(m.from_user_id), content=m.content, created_at=m.created_at)

