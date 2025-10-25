from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Conversation, ConversationParticipant, ModAudit


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit")
def audit(conversation_id: str, limit: int = 200, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    # require owner or admin in group; for DM require one participant (sender OK)
    if c.is_group:
        role = db.query(ConversationParticipant).filter(ConversationParticipant.conversation_id == c.id, ConversationParticipant.user_id == user.id).one_or_none()
        if not role or role.role not in ("owner", "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    else:
        if str(c.user_a) != str(user.id) and str(c.user_b) != str(user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    rows = (
        db.query(ModAudit)
        .filter(ModAudit.target_type == "conversation", ModAudit.target_id == conversation_id)
        .order_by(ModAudit.created_at.desc())
        .limit(min(1000, max(1, limit)))
        .all()
    )
    import json
    return [
        {
            "id": str(r.id),
            "actor_user_id": str(r.actor_user_id),
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "meta": (json.loads(r.meta_json) if r.meta_json else {}),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

