import json
from typing import Any, Dict

import httpx

from ..config import settings
from ..database import get_db
from ..models import Device


def _should_push(user_id: str) -> bool:
    try:
        from ..ws import connections
        return not bool(connections.get(str(user_id)))
    except Exception:
        return True


def _fcm_send(token: str, title: str, body: str, data: Dict[str, Any]) -> None:
    if not settings.FCM_SERVER_KEY:
        return
    headers = {
        "Authorization": f"key={settings.FCM_SERVER_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": token,
        "notification": {"title": title, "body": body},
        "data": data,
        "priority": "high",
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            client.post("https://fcm.googleapis.com/fcm/send", headers=headers, content=json.dumps(payload))
    except Exception:
        pass


def send_push(user_id: str, title: str, body: str, data: Dict[str, Any] | None = None) -> None:
    if settings.PUSH_PROVIDER == "none":
        return
    if not _should_push(user_id):
        return
    tokens: list[str] = []
    for db in get_db():
        try:
            rows = db.query(Device).filter(Device.user_id == user_id, Device.push_token.isnot(None)).all()
            tokens = [d.push_token for d in rows if d.push_token]
        except Exception:
            pass
        break
    data = data or {}
    for tok in tokens:
        if settings.PUSH_PROVIDER == "fcm":
            _fcm_send(tok, title, body, data)
        # apns: omitted for brevity (would need JWT certs or p8)

