import uuid


def unique_phone(prefix: str, digits: int = 5) -> str:
    """Return a unique phone number using the given prefix and number of random digits."""
    suffix = str(uuid.uuid4().int % (10 ** digits)).zfill(digits)
    if prefix.startswith('+'):
        return f"{prefix}{suffix}"
    return f"+963{prefix}{suffix}"
