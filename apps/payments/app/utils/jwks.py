from __future__ import annotations
import os
from typing import Any, Dict
from .hmacsig import verify_hmac_and_prevent_replay  # not used here; placeholder to avoid linter
from ..config import settings

_rsa_private_pem: bytes | None = None
_rsa_public_pem: bytes | None = None


def _ensure_keys() -> None:
    global _rsa_private_pem, _rsa_public_pem
    if settings.JWT_ALG.upper() != 'RS256':
        return
    if _rsa_private_pem is not None and _rsa_public_pem is not None:
        return
    pem = settings.JWT_RS_PRIVATE_PEM
    if pem:
        _rsa_private_pem = pem.encode('utf-8')
    else:
        # DEV: generate ephemeral RSA key
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _rsa_private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    # derive public
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    private_key = serialization.load_pem_private_key(_rsa_private_pem, password=None)
    public_key = private_key.public_key()
    _rsa_public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def get_private_key_pem() -> bytes | None:
    _ensure_keys()
    return _rsa_private_pem


def get_jwks() -> Dict[str, Any]:
    if settings.JWT_ALG.upper() != 'RS256':
        return {"keys": []}
    _ensure_keys()
    from jwcrypto import jwk
    key = jwk.JWK.from_pem(_rsa_public_pem)  # type: ignore[arg-type]
    key_dict = key.export(as_dict=True)
    key_dict['alg'] = 'RS256'
    key_dict['use'] = 'sig'
    key_dict['kid'] = settings.JWT_KEY_ID
    return {"keys": [key_dict]}

