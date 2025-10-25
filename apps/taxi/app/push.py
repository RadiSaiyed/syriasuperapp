from __future__ import annotations
import os
import httpx
from typing import Iterable, Optional, Dict, Any
from sqlalchemy.orm import Session
from .models import DeviceToken


def fcm_send(
    token: str,
    title: str,
    body: str,
    server_key: str,
    data: Optional[Dict[str, Any]] = None,
    content_available: bool = False,
) -> None:
    url = "https://fcm.googleapis.com/fcm/send"
    headers = {"Authorization": f"key={server_key}", "Content-Type": "application/json"}
    payload: Dict[str, Any] = {
        "to": token,
        "notification": {"title": title, "body": body},
        "priority": "high",
    }
    # Attach data payload so the app can act on it directly
    if data:
        payload["data"] = data
    # Optional iOS silent update hint
    if content_available:
        payload["content_available"] = True
    try:
        with httpx.Client(timeout=3.0) as c:
            r = c.post(url, json=payload, headers=headers)
            r.raise_for_status()
    except Exception:
        # swallow in MVP
        pass


def send_push_to_tokens(
    tokens: Iterable[str],
    title: str,
    body: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    content_available: bool = False,
) -> None:
    server_key = os.getenv("FCM_SERVER_KEY", "").strip()
    if not server_key:
        return
    for tok in tokens:
        fcm_send(tok, title, body, server_key, data=data, content_available=content_available)


def send_push_to_user(
    db: Session,
    user_id: str,
    title: str,
    body: str,
    app_mode: str | None = None,
    *,
    data: Optional[Dict[str, Any]] = None,
    content_available: bool = False,
) -> None:
    q = db.query(DeviceToken).filter(DeviceToken.user_id == user_id, DeviceToken.enabled == True)  # noqa: E712
    if app_mode:
        q = q.filter(DeviceToken.app_mode == app_mode)
    tokens = [row.token for row in q.all()]
    if tokens:
        send_push_to_tokens(tokens, title, body, data=data, content_available=content_available)
