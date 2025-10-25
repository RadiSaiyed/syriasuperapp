from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
import uuid
from ..database import get_db
from ..models import User, Conversation, Message, Attachment, Reaction, Block, MessageReceipt
from ..schemas import (
    SendMessageIn,
    MessageOut,
    InboxOut,
    ConversationsOut,
    ConversationOut,
    AttachmentCreateIn,
    AttachmentOut,
    AttachmentsOut,
    ReactionCreateIn,
    ReactionOut,
    ReactionsOut,
    TypingIn,
    ConversationsSummaryOut,
    ConversationSummary,
)
from fastapi import Request
from datetime import datetime, timedelta

# In-memory WS registry provided by ws.py
try:
    from ..ws import deliver_to_user
except Exception:  # pragma: no cover
    def deliver_to_user(user_id: str, payload: dict):
        pass


router = APIRouter(prefix="/messages", tags=["messages"])


def _conv_key(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a.bytes < b.bytes else (b, a)


def _to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=str(m.id), conversation_id=str(m.conversation_id), sender_user_id=str(m.sender_user_id), sender_device_id=m.sender_device_id, recipient_user_id=str(m.recipient_user_id), ciphertext=m.ciphertext, delivered=m.delivered, read=m.read, sent_at=m.sent_at,
    )


@router.post("/send", response_model=MessageOut)
def send_message(payload: SendMessageIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Per-user quota
    try:
        window = datetime.utcnow() - timedelta(seconds=60)
        cnt = db.query(Message).filter(Message.sender_user_id == user.id, Message.sent_at >= window).count()
        from ..config import settings
        if cnt >= settings.CHAT_USER_MSGS_PER_MINUTE:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        pass
    if str(user.id) == payload.recipient_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send to self")
    try:
        recipient_uuid = uuid.UUID(payload.recipient_user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recipient id")
    # Check block lists (either direction)
    if db.query(Block).filter(Block.user_id == user.id, Block.blocked_user_id == recipient_uuid).one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recipient blocked")
    if db.query(Block).filter(Block.user_id == recipient_uuid, Block.blocked_user_id == user.id).one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are blocked")

    a, b = _conv_key(user.id, recipient_uuid)
    convo = db.query(Conversation).filter(Conversation.user_a == a, Conversation.user_b == b).one_or_none()
    if convo is None:
        convo = Conversation(user_a=a, user_b=b)
        db.add(convo)
        db.flush()
    m = Message(conversation_id=convo.id, sender_user_id=user.id, sender_device_id=payload.sender_device_id, recipient_user_id=payload.recipient_user_id, ciphertext=payload.ciphertext)
    db.add(m)
    db.flush()
    # Initialize per-device receipts for recipient
    try:
        from ..models import Device
        devices = db.query(Device).filter(Device.user_id == recipient_uuid).all()
        from datetime import datetime
        for d in devices:
            db.add(MessageReceipt(message_id=m.id, user_id=recipient_uuid, device_id=d.device_id, delivered=False, read=False))
    except Exception:
        pass
    # update convo last message
    convo.last_message_at = m.sent_at

    # attempt real-time delivery
    try:
        deliver_to_user(payload.recipient_user_id, {"type": "message", "message": _to_out(m).model_dump()})
    except Exception:
        pass
    # Push if offline
    try:
        from ..utils.push import send_push
        send_push(str(m.recipient_user_id), title="New message", body="You have a new message", data={"conversation_id": str(m.conversation_id), "message_id": str(m.id)})
    except Exception:
        pass
    # Emit events (no ciphertext in webhook payload)
    try:
        from ..utils.notify import notify
        from ..utils.webhooks import send_webhooks
        notify("chat.message.created", {"message_id": str(m.id), "conversation_id": str(m.conversation_id), "sender_user_id": str(m.sender_user_id), "recipient_user_id": str(m.recipient_user_id)})
        send_webhooks(db, "chat.message.created", {"message_id": str(m.id), "conversation_id": str(m.conversation_id), "sender_user_id": str(m.sender_user_id), "recipient_user_id": str(m.recipient_user_id)})
    except Exception:
        pass
    return _to_out(m)


@router.post("/send_group")
def send_group(conversation_id: str, sender_device_id: str, ciphertext: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    # Check membership
    from ..models import ConversationParticipant
    me = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if not me:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    # Quota per group per user
    try:
        from ..config import settings
        window = datetime.utcnow() - timedelta(seconds=60)
        cnt = db.query(Message).filter(Message.conversation_id == c.id, Message.sender_user_id == user.id, Message.sent_at >= window).count()
        if cnt >= settings.CHAT_GROUP_MSGS_PER_MINUTE:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Group rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        pass

    # Deliver to all members except sender by creating individual messages
    members = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id).all()
    created_ids = []
    for p in members:
        if str(p.user_id) == str(user.id):
            continue
        m = Message(conversation_id=c.id, sender_user_id=user.id, sender_device_id=sender_device_id, recipient_user_id=p.user_id, ciphertext=ciphertext)
        db.add(m)
        db.flush()
        # receipts init for each recipient device
        try:
            from ..models import Device
            devs = db.query(Device).filter(Device.user_id == p.user_id).all()
            for d in devs:
                db.add(MessageReceipt(message_id=m.id, user_id=p.user_id, device_id=d.device_id, delivered=False, read=False))
        except Exception:
            pass
        created_ids.append(str(m.id))
        try:
            deliver_to_user(str(p.user_id), {"type": "message", "message": _to_out(m).model_dump()})
        except Exception:
            pass
        try:
            from ..utils.push import send_push
            send_push(str(p.user_id), title=c.name or "New group message", body="You have a new message", data={"conversation_id": str(c.id), "message_id": str(m.id)})
        except Exception:
            pass
    c.last_message_at = (db.get(Message, created_ids[-1]).sent_at) if created_ids else c.last_message_at
    try:
        from ..utils.notify import notify
        from ..utils.webhooks import send_webhooks
        notify("chat.group.message.created", {"conversation_id": str(c.id), "sender_user_id": str(user.id), "count": len(created_ids)})
        send_webhooks(db, "chat.group.message.created", {"conversation_id": str(c.id), "sender_user_id": str(user.id), "count": len(created_ids)})
    except Exception:
        pass
    return {"detail": "ok", "message_ids": created_ids}


@router.get("/inbox", response_model=InboxOut)
def inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Message).filter(Message.recipient_user_id == user.id, Message.delivered == False).order_by(Message.sent_at.asc()).limit(200).all()  # noqa: E712
    return InboxOut(messages=[_to_out(m) for m in rows])


@router.post("/export")
def export_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or (str(c.user_a) != str(user.id) and str(c.user_b) != str(user.id) and not c.is_group):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # group membership check
    if c.is_group:
        from ..models import ConversationParticipant
        if not db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    msgs = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.sent_at.asc()).all()
    out_msgs = [
        {
            "id": str(m.id),
            "sender_user_id": str(m.sender_user_id),
            "sender_device_id": m.sender_device_id,
            "recipient_user_id": str(m.recipient_user_id),
            "ciphertext": m.ciphertext,
            "delivered": m.delivered,
            "read": m.read,
            "sent_at": m.sent_at.isoformat(),
        }
        for m in msgs
    ]
    # attachments metadata only
    atts = db.query(Attachment).filter(Attachment.message_id.in_([m.id for m in msgs])).all()
    out_atts = [
        {
            "id": str(a.id),
            "message_id": str(a.message_id),
            "content_type": a.content_type,
            "filename": a.filename,
            "size_bytes": a.size_bytes,
            "ciphertext_b64": a.ciphertext_b64,
            "created_at": a.created_at.isoformat(),
        }
        for a in atts
    ]
    return {"version": 1, "conversation_id": str(c.id), "is_group": bool(c.is_group), "messages": out_msgs, "attachments": out_atts}


@router.post("/import")
def import_conversation(conversation_id: str, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or (str(c.user_a) != str(user.id) and str(c.user_b) != str(user.id) and not c.is_group):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # Only import as local history (no delivery to others); mark delivered+read
    items = payload.get("messages", [])
    created = []
    for it in items:
        ct = it.get("ciphertext")
        ts = it.get("sent_at")
        sd = it.get("sender_device_id") or "import"
        if not ct:
            continue
        try:
            when = datetime.fromisoformat(ts) if ts else datetime.utcnow()
        except Exception:
            when = datetime.utcnow()
        m = Message(conversation_id=c.id, sender_user_id=user.id, sender_device_id=sd, recipient_user_id=user.id, ciphertext=ct, delivered=True, read=True, sent_at=when)
        db.add(m)
        db.flush()
        created.append(str(m.id))
    return {"detail": "ok", "created": created}


@router.post("/{message_id}/ack_delivered")
def ack_delivered(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or str(m.recipient_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    m.delivered = True
    try:
        deliver_to_user(str(m.sender_user_id), {"type": "delivered", "message_id": str(m.id)})
    except Exception:
        pass
    try:
        from ..utils.notify import notify
        notify("chat.message.delivered", {"message_id": str(m.id)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/{message_id}/ack_read")
def ack_read(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or str(m.recipient_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    m.read = True
    try:
        deliver_to_user(str(m.sender_user_id), {"type": "read", "message_id": str(m.id)})
    except Exception:
        pass
    try:
        from ..utils.notify import notify
        notify("chat.message.read", {"message_id": str(m.id)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/{message_id}/ack_delivered_device")
def ack_delivered_device(message_id: str, device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or str(m.recipient_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    # Ensure device belongs to user
    from ..models import Device
    dev = db.query(Device).filter(Device.user_id == user.id, Device.device_id == device_id).one_or_none()
    if not dev:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid device")
    r = db.query(MessageReceipt).filter(MessageReceipt.message_id == m.id, MessageReceipt.device_id == device_id).one_or_none()
    if r is None:
        from datetime import datetime
        r = MessageReceipt(message_id=m.id, user_id=user.id, device_id=device_id, delivered=True, delivered_at=datetime.utcnow())
        db.add(r)
    else:
        from datetime import datetime
        r.delivered = True
        r.delivered_at = datetime.utcnow()
    # Aggregate flag (any device)
    m.delivered = True
    try:
        deliver_to_user(str(m.sender_user_id), {"type": "delivered", "message_id": str(m.id), "device_id": device_id})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/{message_id}/ack_read_device")
def ack_read_device(message_id: str, device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or str(m.recipient_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    from ..models import Device
    dev = db.query(Device).filter(Device.user_id == user.id, Device.device_id == device_id).one_or_none()
    if not dev:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid device")
    r = db.query(MessageReceipt).filter(MessageReceipt.message_id == m.id, MessageReceipt.device_id == device_id).one_or_none()
    from datetime import datetime
    if r is None:
        r = MessageReceipt(message_id=m.id, user_id=user.id, device_id=device_id, read=True, read_at=datetime.utcnow())
        db.add(r)
    else:
        r.read = True
        r.read_at = datetime.utcnow()
    m.read = True
    try:
        deliver_to_user(str(m.sender_user_id), {"type": "read", "message_id": str(m.id), "device_id": device_id})
    except Exception:
        pass
    return {"detail": "ok"}


@router.get("/{message_id}/receipts")
def list_receipts(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    rows = db.query(MessageReceipt).filter(MessageReceipt.message_id == m.id).order_by(MessageReceipt.created_at.asc()).all()
    return [
        {
            "device_id": r.device_id,
            "delivered": r.delivered,
            "read": r.read,
            "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
            "read_at": r.read_at.isoformat() if r.read_at else None,
        }
        for r in rows
    ]


@router.get("/conversations", response_model=ConversationsOut)
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convos = (
        db.query(Conversation)
        .filter((Conversation.user_a == user.id) | (Conversation.user_b == user.id))
        .order_by(Conversation.last_message_at.desc())
        .limit(100)
        .all()
    )
    return ConversationsOut(
        conversations=[
            ConversationOut(id=str(c.id), user_a=str(c.user_a), user_b=str(c.user_b), last_message_at=c.last_message_at)
            for c in convos
        ]
    )


@router.get("/history", response_model=InboxOut)
def history(conversation_id: str, before: str | None = None, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ensure membership
    c = db.get(Conversation, conversation_id)
    if not c or (str(c.user_a) != str(user.id) and str(c.user_b) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    q = db.query(Message).filter(Message.conversation_id == c.id)
    if before:
        from datetime import datetime

        try:
            ts = datetime.fromisoformat(before)
            q = q.filter(Message.sent_at < ts)
        except Exception:
            pass
    rows = q.order_by(Message.sent_at.desc()).limit(min(200, max(1, limit))).all()
    rows = list(reversed(rows))
    return InboxOut(messages=[_to_out(m) for m in rows])


@router.post("/{message_id}/attachments", response_model=AttachmentOut)
def add_attachment(message_id: str, payload: AttachmentCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    data_b64 = payload.ciphertext_b64
    size = int(len(data_b64) * 3 / 4)
    a = Attachment(message_id=m.id, content_type=payload.content_type or None, filename=payload.filename or None, size_bytes=size, ciphertext_b64=data_b64)
    db.add(a)
    db.flush()
    try:
        deliver_to_user(str(m.recipient_user_id), {"type": "attachment", "message_id": str(m.id), "attachment_id": str(a.id)})
    except Exception:
        pass
    try:
        from ..utils.notify import notify
        notify("chat.attachment.added", {"message_id": str(m.id), "attachment_id": str(a.id)})
    except Exception:
        pass
    return AttachmentOut(id=str(a.id), message_id=str(a.message_id), content_type=a.content_type, filename=a.filename, size_bytes=a.size_bytes, ciphertext_b64=a.ciphertext_b64, created_at=a.created_at, download_url=None)


@router.get("/{message_id}/attachments", response_model=AttachmentsOut)
def list_attachments(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    items = db.query(Attachment).filter(Attachment.message_id == m.id).order_by(Attachment.created_at.asc()).all()
    return AttachmentsOut(
        attachments=[
            AttachmentOut(
                id=str(a.id),
                message_id=str(a.message_id),
                content_type=a.content_type,
                filename=a.filename,
                size_bytes=a.size_bytes,
                ciphertext_b64=a.ciphertext_b64,
                created_at=a.created_at,
                download_url=(f"/messages/attachments/blob/{a.id}" if a.blob_id else None),
            )
            for a in items
        ]
    )


@router.post("/{message_id}/attachments/upload")
async def upload_attachment(message_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    body = await request.body()
    size = len(body)
    from ..models import Blob
    blob = Blob(data=body, size_bytes=size)
    db.add(blob)
    db.flush()
    # create attachment record
    ct = request.headers.get("X-Content-Type") or None
    fn = request.headers.get("X-Filename") or None
    a = Attachment(message_id=m.id, content_type=ct, filename=fn, size_bytes=size, ciphertext_b64="", blob_id=blob.id)
    db.add(a)
    db.flush()
    try:
        deliver_to_user(str(m.recipient_user_id), {"type": "attachment", "message_id": str(m.id), "attachment_id": str(a.id)})
    except Exception:
        pass
    return {"id": str(a.id), "download_url": f"/messages/attachments/blob/{a.id}"}


@router.get("/attachments/blob/{attachment_id}")
def download_blob(attachment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Attachment, attachment_id)
    if not a:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    m = db.get(Message, a.message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    from ..models import Blob
    b = db.get(Blob, a.blob_id) if a.blob_id else None
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No blob")
    from fastapi import Response
    return Response(content=b.data, media_type=a.content_type or "application/octet-stream", headers={"Content-Disposition": f"attachment; filename=\"{a.filename or 'file.bin'}\""})


@router.post("/typing")
def typing(payload: TypingIn, user: User = Depends(get_current_user)):
    peer: str | None = None
    if payload.peer_user_id:
        peer = payload.peer_user_id
    elif payload.conversation_id:
        # infer peer from conversation id encoded roles
        try:
            convo_id = payload.conversation_id
            # cannot DB load without session here; quick path omitted
            peer = None
        except Exception:
            peer = None
    if not peer:
        return {"detail": "ok"}
    try:
        deliver_to_user(str(peer), {"type": "typing", "from": str(user.id), "is_typing": bool(payload.is_typing)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.post("/{message_id}/reactions", response_model=ReactionOut)
def add_reaction(message_id: str, payload: ReactionCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    r = db.query(Reaction).filter(Reaction.message_id == m.id, Reaction.user_id == user.id, Reaction.emoji == payload.emoji).one_or_none()
    if r is None:
        r = Reaction(message_id=m.id, user_id=user.id, emoji=payload.emoji)
        db.add(r)
        db.flush()
    try:
        other = m.recipient_user_id if str(m.sender_user_id) == str(user.id) else m.sender_user_id
        deliver_to_user(str(other), {"type": "reaction", "message_id": str(m.id), "emoji": r.emoji, "user_id": str(user.id)})
    except Exception:
        pass
    return ReactionOut(id=str(r.id), message_id=str(r.message_id), user_id=str(r.user_id), emoji=r.emoji, created_at=r.created_at)


@router.get("/{message_id}/reactions", response_model=ReactionsOut)
def list_reactions(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    rows = db.query(Reaction).filter(Reaction.message_id == m.id).order_by(Reaction.created_at.asc()).all()
    return ReactionsOut(reactions=[ReactionOut(id=str(x.id), message_id=str(x.message_id), user_id=str(x.user_id), emoji=x.emoji, created_at=x.created_at) for x in rows])


@router.delete("/{message_id}/reactions")
def remove_reaction(message_id: str, emoji: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or (str(m.sender_user_id) != str(user.id) and str(m.recipient_user_id) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    r = db.query(Reaction).filter(Reaction.message_id == m.id, Reaction.user_id == user.id, Reaction.emoji == emoji).one_or_none()
    if r:
        db.delete(r)
    try:
        other = m.recipient_user_id if str(m.sender_user_id) == str(user.id) else m.sender_user_id
        deliver_to_user(str(other), {"type": "reaction_removed", "message_id": str(m.id), "emoji": emoji, "user_id": str(user.id)})
    except Exception:
        pass
    return {"detail": "ok"}


@router.get("/conversations_summary", response_model=ConversationsSummaryOut)
def conversations_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import or_, and_
    convos = (
        db.query(Conversation)
        .filter(or_(Conversation.user_a == user.id, Conversation.user_b == user.id))
        .order_by(Conversation.last_message_at.desc())
        .limit(100)
        .all()
    )
    out: list[ConversationSummary] = []
    for c in convos:
        unread = db.query(Message).filter(Message.conversation_id == c.id, Message.recipient_user_id == user.id, Message.read == False).count()  # noqa: E712
        out.append(ConversationSummary(id=str(c.id), user_a=str(c.user_a), user_b=str(c.user_b), last_message_at=c.last_message_at, unread_count=int(unread)))
    return ConversationsSummaryOut(conversations=out)


@router.get("/search", response_model=InboxOut)
def search(conversation_id: str, sender_device_id: str | None = None, has_attachments: bool | None = None, since: str | None = None, until: str | None = None, limit: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or (str(c.user_a) != str(user.id) and str(c.user_b) != str(user.id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    q = db.query(Message).filter(Message.conversation_id == c.id)
    if sender_device_id:
        q = q.filter(Message.sender_device_id == sender_device_id)
    if since:
        from datetime import datetime
        try:
            q = q.filter(Message.sent_at >= datetime.fromisoformat(since))
        except Exception:
            pass
    if until:
        from datetime import datetime
        try:
            q = q.filter(Message.sent_at <= datetime.fromisoformat(until))
        except Exception:
            pass
    if has_attachments:
        from sqlalchemy import exists
        q = q.filter(exists().where(Attachment.message_id == Message.id))
    rows = q.order_by(Message.sent_at.desc()).limit(min(200, max(1, limit))).all()
    rows = list(reversed(rows))
    return InboxOut(messages=[_to_out(m) for m in rows])


@router.delete("/{message_id}")
def delete_message_in_group(message_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    c = db.get(Conversation, m.conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a group message")
    from ..models import ConversationParticipant
    role = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if not role or role.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    db.delete(m)
    record_mod_event(db, str(user.id), "group.message.delete", "message", str(m.id), {"conversation_id": str(c.id)})
    try:
        deliver_to_user(str(m.sender_user_id), {"type": "message_deleted", "message_id": str(m.id)})
        deliver_to_user(str(m.recipient_user_id), {"type": "message_deleted", "message_id": str(m.id)})
    except Exception:
        pass
    return {"detail": "ok"}
