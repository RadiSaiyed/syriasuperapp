import time
import httpx
import jwt
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
    unverified = jwt.get_unverified_header(token)
    kid = unverified.get('kid')
    jwks = _fetch_jwks(jwks_url)
    keys = jwks.get('keys', [])
    public_key = None
    for k in keys:
        if kid is None or k.get('kid') == kid:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(k)
            break
    if public_key is None:
        raise jwt.InvalidTokenError('No matching key')
    options = {"require": ["exp", "iat", "sub"], "verify_aud": audience is not None}
    return jwt.decode(token, public_key, algorithms=["RS256"], audience=audience, issuer=issuer, options=options)

