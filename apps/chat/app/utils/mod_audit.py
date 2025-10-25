import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..models import ModAudit


def record_mod_event(db: Session, actor_user_id: str, action: str, target_type: str, target_id: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    try:
        row = ModAudit(actor_user_id=actor_user_id, action=action, target_type=target_type, target_id=target_id, meta_json=json.dumps(meta or {}))
        db.add(row)
        db.flush()
    except Exception:
        db.rollback()
        try:
            db.commit()
        except Exception:
            pass

