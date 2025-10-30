import hashlib
import json
from datetime import datetime
from typing import Any, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models import IdempotencyKey


def body_sha256(payload: Any) -> str:
    try:
        if hasattr(payload, "model_dump"):
            obj = payload.model_dump()
        else:
            obj = payload
        data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    except Exception:
        data = b""
    return hashlib.sha256(data).hexdigest()


def reserve(db: Session, user_id: str, method: str, path: str, key: str, payload: Any) -> Tuple[IdempotencyKey, str]:
    """Reserve an idempotency key for a given request fingerprint.

    Returns (record, state) where state is one of: "reserved", "pending", "replay".
    - reserved: new record created (proceed to process)
    - pending: existing record found but not completed yet (proceed cautiously)
    - replay: completed record exists; safe to return the previous result
    If a conflicting fingerprint is found for the same key, raises 409.
    """
    method = (method or "").upper()[:8]
    path = (path or "")[:256]
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing idempotency key")
    fp = body_sha256(payload)

    rec = (
        db.query(IdempotencyKey)
        .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
        .one_or_none()
    )
    if rec:
        if rec.method != method or rec.path != path or rec.body_hash != fp:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key conflict for different request",
            )
        return rec, ("replay" if (rec.status == "completed" and rec.result_ref) else "pending")
    try:
        rec = IdempotencyKey(
            user_id=user_id,
            key=key,
            method=method,
            path=path,
            body_hash=fp,
            status="in_progress",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(rec)
        db.flush()
        return rec, "reserved"
    except IntegrityError:
        db.rollback()
        rec = (
            db.query(IdempotencyKey)
            .filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
            .one_or_none()
        )
        if rec is None:
            raise
        if rec.method != method or rec.path != path or rec.body_hash != fp:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key conflict for different request",
            )
        return rec, ("replay" if (rec.status == "completed" and rec.result_ref) else "pending")


def finalize(db: Session, rec: IdempotencyKey, result_ref: str | None) -> None:
    rec.status = "completed"
    rec.result_ref = result_ref
    rec.updated_at = datetime.utcnow()
    db.flush()

