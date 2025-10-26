import hashlib
import json
from typing import Any


def compute_etag(obj: Any) -> str:
    try:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    except Exception:
        data = str(obj)
    h = hashlib.sha256(data.encode("utf-8", "ignore")).hexdigest()
    return f"W/\"{h}\""

