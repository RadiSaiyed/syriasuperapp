import json
from typing import Any, Optional
from sqlalchemy.orm import Session

from ..models import AuditLog


def audit(db: Session, *, user_id: Optional[str], action: str, entity_type: str, entity_id: Optional[str], before: Any = None, after: Any = None) -> None:
    try:
        al = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before_json=json.dumps(before, default=str)[:4096] if before is not None else None,
            after_json=json.dumps(after, default=str)[:4096] if after is not None else None,
        )
        db.add(al)
    except Exception:
        # best-effort, never block write path
        pass

