import time
import httpx
import jwt
from jwt import PyJWKClient
from typing import Any, Dict

_CACHE: dict[str, tuple[float, Dict[str, Any]]] = {}


def _fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    now = time.time()
    entry = _CACHE.get(jwks_url)
    if entry and now - entry[0] < 300:
        return entry[1]
    with httpx.Client(timeout=3.0) as c:
        r = c.get(jwks_url)
        r.raise_for_status()
        data = r.json()
        _CACHE[jwks_url] = (now, data)
        return data


def decode_with_jwks(token: str, jwks_url: str, audience: str | None = None, issuer: str | None = None) -> Dict[str, Any]:
    # Use PyJWT's JWK client to pick correct key by kid
    client = PyJWKClient(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token).key
    options = {"require": ["exp", "iat", "sub"], "verify_aud": audience is not None}
    return jwt.decode(token, signing_key, algorithms=["RS256"], audience=audience, issuer=issuer, options=options)
