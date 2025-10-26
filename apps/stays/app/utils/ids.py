from uuid import UUID


def as_uuid(value):
    try:
        return UUID(str(value))
    except Exception:
        return value

