from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Conversation, ConversationParticipant, User, GroupInvite
from ..models import Blob
from fastapi import Request, Response
from ..utils.mod_audit import record_mod_event
from ..config import settings


router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("")
def create_group(name: str, member_user_ids: list[str] | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Create conversation flagged as group
    convo = Conversation(user_a=user.id, user_b=user.id, is_group=True, name=name, owner_user_id=user.id)
    db.add(convo)
    db.flush()
    # Add participants (owner included)
    db.add(ConversationParticipant(conversation_id=convo.id, user_id=user.id, role="owner"))
    if member_user_ids:
        for uid in member_user_ids:
            if uid == str(user.id):
                continue
            u = db.get(User, uid)
            if u:
                db.add(ConversationParticipant(conversation_id=convo.id, user_id=u.id, role="member"))
    record_mod_event(db, str(user.id), "group.create", "conversation", str(convo.id), {"name": name, "members": member_user_ids or []})
    return {"id": str(convo.id), "name": convo.name}


@router.patch("/{conversation_id}")
def rename_group(conversation_id: str, name: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    c.name = name
    record_mod_event(db, str(user.id), "group.rename", "conversation", str(c.id), {"name": name})
    return {"detail": "ok"}


@router.post("/{conversation_id}/members")
def add_members(conversation_id: str, member_user_ids: list[str], user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    # Only owner or admin can add
    role = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if not role or role.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    for uid in member_user_ids:
        u = db.get(User, uid)
        if u and not db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == u.id).one_or_none():
            db.add(ConversationParticipant(conversation_id=c.id, user_id=u.id, role="member"))
    record_mod_event(db, str(user.id), "group.add_members", "conversation", str(c.id), {"members": member_user_ids})
    return {"detail": "ok"}


@router.delete("/{conversation_id}/members/{member_user_id}")
def remove_member(conversation_id: str, member_user_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    role = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if not role or role.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    row = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == member_user_id).one_or_none()
    if row:
        db.delete(row)
    record_mod_event(db, str(user.id), "group.remove_member", "conversation", str(c.id), {"member": member_user_id})
    return {"detail": "ok"}


@router.post("/{conversation_id}/leave")
def leave_group(conversation_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    row = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if row:
        db.delete(row)
    record_mod_event(db, str(user.id), "group.leave", "conversation", str(c.id))
    return {"detail": "ok"}


@router.get("")
def my_groups(user=Depends(get_current_user), db: Session = Depends(get_db)):
    conv_ids = [cid for (cid,) in db.query(ConversationParticipant.conversation_id).filter(ConversationParticipant.user_id == user.id).all()]
    if not conv_ids:
        return []
    groups = db.query(Conversation).filter(Conversation.id.in_(conv_ids), Conversation.is_group == True).order_by(Conversation.last_message_at.desc()).all()  # noqa: E712
    out = []
    for g in groups:
        cnt = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == g.id).count()
        out.append({"id": str(g.id), "name": g.name, "member_count": int(cnt), "last_message_at": g.last_message_at.isoformat()})
    return out


@router.post("/{conversation_id}/avatar/url")
def set_avatar_url(conversation_id: str, url: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    c.avatar_url = url
    c.avatar_blob_id = None
    record_mod_event(db, str(user.id), "group.avatar_url", "conversation", str(c.id), {"url": url})
    return {"detail": "ok"}


@router.post("/{conversation_id}/avatar/upload")
async def upload_avatar(conversation_id: str, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty body")
    blob = Blob(data=body, size_bytes=len(body))
    db.add(blob)
    db.flush()
    c.avatar_blob_id = blob.id
    c.avatar_url = None
    record_mod_event(db, str(user.id), "group.avatar_upload", "conversation", str(c.id), {"size": len(body)})
    return {"detail": "ok"}


@router.get("/{conversation_id}/avatar")
def get_avatar(conversation_id: str, db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if c.avatar_url:
        return {"url": c.avatar_url}
    if c.avatar_blob_id:
        b = db.get(Blob, c.avatar_blob_id)
        if b:
            return Response(content=b.data, media_type="image/jpeg")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No avatar")


@router.post("/{conversation_id}/members/{member_user_id}/role")
def set_member_role(conversation_id: str, member_user_id: str, role: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    if role not in ("admin", "member"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    row = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == member_user_id).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in group")
    row.role = role
    record_mod_event(db, str(user.id), "group.set_role", "conversation", str(c.id), {"member": member_user_id, "role": role})
    return {"detail": "ok"}


@router.post("/{conversation_id}/transfer_ownership")
def transfer_ownership(conversation_id: str, new_owner_user_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    row = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == new_owner_user_id).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in group")
    c.owner_user_id = row.user_id
    row.role = "owner"  # optional, keep role semantics simple
    record_mod_event(db, str(user.id), "group.transfer_ownership", "conversation", str(c.id), {"new_owner": new_owner_user_id})
    return {"detail": "ok"}


@router.post("/{conversation_id}/archive")
def archive_group(conversation_id: str, archived: bool = True, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if str(c.owner_user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner")
    c.archived = bool(archived)
    from datetime import datetime
    c.archived_at = datetime.utcnow() if c.archived else None
    record_mod_event(db, str(user.id), "group.archive", "conversation", str(c.id), {"archived": bool(archived)})
    return {"detail": "ok"}


def _gen_code() -> str:
    import secrets
    return secrets.token_urlsafe(16)


@router.post("/{conversation_id}/invites")
def create_invite(conversation_id: str, expires_in_minutes: int | None = None, max_uses: int = 0, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    role = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
    if not role or role.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    from datetime import datetime, timedelta
    exp = None
    if isinstance(expires_in_minutes, int) and expires_in_minutes > 0:
        exp = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
    inv = GroupInvite(conversation_id=c.id, code=_gen_code(), created_by_user_id=user.id, expires_at=exp, max_uses=max_uses)
    db.add(inv)
    db.flush()
    record_mod_event(db, str(user.id), "group.invite.create", "conversation", str(c.id), {"code": inv.code, "expires_at": inv.expires_at.isoformat() if inv.expires_at else None, "max_uses": max_uses})
    return {"code": inv.code, "expires_at": inv.expires_at.isoformat() if inv.expires_at else None, "max_uses": inv.max_uses}


@router.get("/invites/{code}")
def preview_invite(code: str, db: Session = Depends(get_db)):
    inv = db.query(GroupInvite).filter(GroupInvite.code == code).one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    c = db.get(Conversation, inv.conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite")
    from datetime import datetime
    if inv.expires_at and datetime.utcnow() > inv.expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Expired")
    remaining = None if inv.max_uses == 0 else max(0, inv.max_uses - inv.used_count)
    return {"conversation_id": str(c.id), "name": c.name, "remaining": remaining}


@router.post("/invites/{code}/accept")
def accept_invite(code: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    inv = db.query(GroupInvite).filter(GroupInvite.code == code).one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    c = db.get(Conversation, inv.conversation_id)
    if not c or not c.is_group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite")
    from datetime import datetime
    if inv.expires_at and datetime.utcnow() > inv.expires_at:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Expired")
    if inv.max_uses and inv.used_count >= inv.max_uses:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Invite exhausted")
    # add member if not present
    if not db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none():
        db.add(ConversationParticipant(conversation_id=c.id, user_id=user.id, role="member"))
    inv.used_count += 1
    record_mod_event(db, str(user.id), "group.invite.accept", "conversation", str(c.id), {"code": code})
    return {"detail": "ok", "conversation_id": str(c.id)}


@router.get("/invites/{code}/deeplink")
def invite_deeplink(code: str):
    uri = f"superapp://chat/invite?code={code}"
    web = f"{settings.CHAT_PUBLIC_BASE_URL.rstrip('/')}/chat/invite?code={code}"
    return {"uri": uri, "web_url": web}
