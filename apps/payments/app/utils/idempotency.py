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

