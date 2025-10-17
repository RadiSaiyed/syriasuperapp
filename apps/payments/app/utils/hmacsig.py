from superapp_shared.internal_hmac import verify_internal_hmac_with_replay
from ..config import settings


def verify_hmac_and_prevent_replay(ts: str, body: dict, sign: str, *, ttl_override: int | None = None) -> bool:
    ttl = getattr(settings, "INTERNAL_HMAC_TTL_SECS", 60) if ttl_override is None else ttl_override
    return verify_internal_hmac_with_replay(
        ts,
        body,
        sign,
        secret=settings.INTERNAL_API_SECRET,
        redis_url=getattr(settings, "REDIS_URL", None),
        ttl_secs=ttl,
    )
