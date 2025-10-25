#!/usr/bin/env python3
"""
Send a weekly digest via the AI Gateway to the Chat inbox for a user.

Env:
  AI_GATEWAY_BASE_URL (default http://localhost:8099)
  CHAT_USER_JWT  (Bearer token for Chat)
  USER_ID        (UUID of target user)
  UTILITIES_BASE_URL (optional; default http://localhost:8084)
  UTILITIES_USER_JWT (optional; to fetch bills)

Usage:
  USER_ID=<uuid> CHAT_USER_JWT="Bearer ..." python tools/send_weekly_digest.py
"""
from __future__ import annotations

import os
import httpx


def fetch_utilities_items() -> list[dict]:
    base = os.getenv("UTILITIES_BASE_URL", "http://localhost:8084")
    tok = os.getenv("UTILITIES_USER_JWT", "")
    if not tok:
        return []
    try:
        with httpx.Client(base_url=base, timeout=5.0) as client:
            r = client.get("/bills")
            if r.status_code >= 400:
                return []
            bills = r.json().get("bills", [])
            out = []
            for b in bills[:3]:
                amt = int(b.get("amount_cents", 0)) / 100.0
                out.append({
                    "title": f"Rechnung {b.get('id', '')}",
                    "detail": f"{amt:.2f} SYP, Fällig: {b.get('due_date', '')}",
                    "link": None,
                })
            return out
    except Exception:
        return []


def main():
    base = os.getenv("AI_GATEWAY_BASE_URL", "http://localhost:8099")
    user_id = os.getenv("USER_ID", "").strip()
    chat_jwt = os.getenv("CHAT_USER_JWT", "").strip()
    if not user_id or not chat_jwt:
        print("Missing USER_ID or CHAT_USER_JWT")
        return 1
    items = []
    items += fetch_utilities_items()
    if not items:
        items = [{"title": "Keine neuen Ereignisse", "detail": "Alles ruhig in dieser Woche"}]
    body = {"user_id": user_id, "items": items}
    with httpx.Client(base_url=base, timeout=5.0, headers={"Authorization": chat_jwt}) as client:
        r = client.post("/v1/digest", json=body)
        print(r.status_code, r.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

