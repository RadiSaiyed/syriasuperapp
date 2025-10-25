from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from ..auth import get_current_user
from ..database import get_db
from ..models import User, Conversation, Message
from .messages import deliver_to_user
from superapp_shared.internal_hmac import verify_internal_hmac_with_replay
from ..config import settings


router = APIRouter(prefix="/internal/tools", tags=["internal_tools"])  # HMAC + user auth


class SystemNotifyIn(BaseModel):
    user_id: str
    text: str


@router.post("/system_notify")
def system_notify(payload: SystemNotifyIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # HMAC check
    ts = request.headers.get("X-Internal-Ts") or ""
    sign = request.headers.get("X-Internal-Sign") or ""
    ok = verify_internal_hmac_with_replay(ts, payload.model_dump(), sign, settings.INTERNAL_API_SECRET, redis_url=settings.REDIS_URL, ttl_secs=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # AuthN must match target user
    if str(user.id) != str(payload.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user mismatch")

    # Find or create a self conversation (user to self) to host system messages
    convo = db.query(Conversation).filter(Conversation.user_a == user.id, Conversation.user_b == user.id).one_or_none()
    if convo is None:
        convo = Conversation(user_a=user.id, user_b=user.id)
        db.add(convo)
        db.flush()
    # Insert message as from 'system' (reuse sender_user_id=user, but mark device id)
    m = Message(conversation_id=convo.id, sender_user_id=user.id, sender_device_id="system", recipient_user_id=user.id, ciphertext=payload.text, delivered=False, read=False)
    db.add(m)
    db.flush()
    try:
        deliver_to_user(str(user.id), {"type": "message", "message": {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "sender_user_id": str(m.sender_user_id),
            "sender_device_id": m.sender_device_id,
            "recipient_user_id": str(m.recipient_user_id),
            "ciphertext": m.ciphertext,
            "delivered": m.delivered,
            "read": m.read,
            "sent_at": m.sent_at.isoformat(),
        }})
    except Exception:
        pass
    return {"detail": "ok", "conversation_id": str(convo.id), "message_id": str(m.id)}


class SystemCardIn(BaseModel):
    user_id: str
    title: str
    action: str
    data: dict | None = None


@router.post("/system_card")
def system_card(payload: SystemCardIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # HMAC check
    ts = request.headers.get("X-Internal-Ts") or ""
    sign = request.headers.get("X-Internal-Sign") or ""
    ok = verify_internal_hmac_with_replay(ts, payload.model_dump(), sign, settings.INTERNAL_API_SECRET, redis_url=settings.REDIS_URL, ttl_secs=60)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if str(user.id) != str(payload.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user mismatch")
    convo = db.query(Conversation).filter(Conversation.user_a == user.id, Conversation.user_b == user.id).one_or_none()
    if convo is None:
        convo = Conversation(user_a=user.id, user_b=user.id)
        db.add(convo)
        db.flush()
    # Encode a lightweight action card in text (client can parse [ACTION]{json})
    import json
    content = f"[ACTION]{json.dumps({'title': payload.title, 'action': payload.action, 'data': payload.data or {}}, separators=(',',':'))}"
    m = Message(conversation_id=convo.id, sender_user_id=user.id, sender_device_id="system", recipient_user_id=user.id, ciphertext=content, delivered=False, read=False)
    db.add(m)
    db.flush()
    try:
        deliver_to_user(str(user.id), {"type": "message", "message": {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "sender_user_id": str(m.sender_user_id),
            "sender_device_id": m.sender_device_id,
            "recipient_user_id": str(m.recipient_user_id),
            "ciphertext": m.ciphertext,
            "delivered": m.delivered,
            "read": m.read,
            "sent_at": m.sent_at.isoformat(),
        }})
    except Exception:
        pass
    return {"detail": "ok", "conversation_id": str(convo.id), "message_id": str(m.id)}
