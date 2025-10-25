from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from ..models import AuditEvent
from .event_stream import publish


def record_event(db: Session, type: str, user_id: Optional[str], data: Optional[Dict[str, Any]] = None) -> None:
    try:
        ev = AuditEvent(type=type, user_id=user_id, data=data or {})
        db.add(ev)
        db.flush()
        try:
            publish(type, data or {})
        except Exception:
            pass
    except Exception:
        # Never break primary flow on audit errors
        db.rollback()
        try:
            db.commit()
        except Exception:
            pass
