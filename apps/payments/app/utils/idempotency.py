from fastapi import Header, HTTPException, status


def require_idempotency_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header"
        )
    if len(idempotency_key) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key too long"
        )
    return idempotency_key


def resolve_idempotency_key(header_value: str | None, body_value: str | None) -> str:
    """Prefer header Idempotency-Key if set; fallback to body value.
    Enforces max length 64 and non-empty.
    """
    key = (header_value or body_value or "").strip()
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing idempotency key")
    if len(key) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency key too long")
    return key
