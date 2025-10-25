from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import User, Listing, Offer, ChatMessage
from ..schemas import ChatMessageIn, ChatMessageOut, ChatMessagesListOut


router = APIRouter(prefix="/chats", tags=["chats"]) 


def _can_chat(db: Session, user: User, listing: Listing) -> bool:
    if listing.seller_user_id == user.id:
        return True
    # Buyers with offers on this listing may chat
    exists = (
        db.query(Offer)
        .filter(Offer.listing_id == listing.id)
        .filter(Offer.buyer_user_id == user.id)
        .first()
    )
    return exists is not None


@router.get("/listing/{listing_id}", response_model=ChatMessagesListOut)
def get_messages(listing_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if not _can_chat(db, user, l):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(ChatMessage).filter(ChatMessage.listing_id == l.id).order_by(ChatMessage.created_at.asc()).limit(200).all()
    return ChatMessagesListOut(messages=[ChatMessageOut(id=str(m.id), listing_id=str(m.listing_id), from_user_id=str(m.from_user_id), to_user_id=str(m.to_user_id) if m.to_user_id else None, content=m.content, created_at=m.created_at) for m in rows])


@router.post("/listing/{listing_id}", response_model=ChatMessageOut)
def post_message(listing_id: str, payload: ChatMessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    l = db.get(Listing, listing_id)
    if l is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if not _can_chat(db, user, l):
        raise HTTPException(status_code=403, detail="Forbidden")
    to_id = payload.to_user_id
    if to_id is None and user.id != l.seller_user_id:
        to_id = l.seller_user_id
    m = ChatMessage(listing_id=l.id, from_user_id=user.id, to_user_id=to_id, content=payload.content.strip())
    db.add(m)
    db.flush()
    return ChatMessageOut(id=str(m.id), listing_id=str(m.listing_id), from_user_id=str(m.from_user_id), to_user_id=str(m.to_user_id) if m.to_user_id else None, content=m.content, created_at=m.created_at)
