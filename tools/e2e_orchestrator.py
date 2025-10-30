#!/usr/bin/env python3
"""
Simple E2E orchestrator to trigger core cross-service flows.

Supported flows:
- commerce_checkout: login, add first product, checkout (creates Payments internal request)
- doctors_appointment (best-effort): login, search first available slot, book appointment

Environment variables:
- COMMERCE_BASE_URL (default http://localhost:8083)
- DOCTORS_BASE_URL (default http://localhost:8086)
- PHONE_A (default +963900000001)
- NAME_A (default Alice)
"""
import os
import sys
import json
import time
from typing import Optional, Tuple

import httpx


def _login_via_otp(base: str, phone: str, name: str) -> str:
    with httpx.Client(timeout=10.0) as c:
        c.post(f"{base}/auth/request_otp", json={"phone": phone}).raise_for_status()
        r = c.post(f"{base}/auth/verify_otp", json={"phone": phone, "otp": "123456", "name": name})
        r.raise_for_status()
        return r.json()["access_token"]


def _h(base: str, token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def flow_commerce_checkout(base: str, phone: str, name: str) -> dict:
    tok = _login_via_otp(base, phone, name)
    with httpx.Client(timeout=10.0) as c:
        shops = c.get(f"{base}/shops", headers=_h(base, tok)).json()
        if not shops:
            return {"flow": "commerce", "status": "no_shops"}
        shop_id = shops[0]["id"]
        prods = c.get(f"{base}/shops/{shop_id}/products", headers=_h(base, tok)).json()
        if not prods:
            return {"flow": "commerce", "status": "no_products"}
        prod_id = prods[0]["id"]
        c.post(f"{base}/cart/items", headers=_h(base, tok), json={"product_id": prod_id, "qty": 1}).raise_for_status()
        r = c.post(f"{base}/orders/checkout", headers=_h(base, tok)).raise_for_status()
        order = r.json()
        return {"flow": "commerce", "status": "ok", "order_id": order.get("id"), "payment_request_id": order.get("payment_request_id")}


def flow_doctors_appointment(base: str, phone: str, name: str) -> dict:
    tok = _login_via_otp(base, phone, name)
    # Search requires a time window; use next 24h
    from datetime import datetime, timedelta, timezone
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=24)
    start_iso = start.isoformat().replace("+00:00", "Z")
    end_iso = end.isoformat().replace("+00:00", "Z")
    with httpx.Client(timeout=10.0) as c:
        payload = {"start_time": start_iso, "end_time": end_iso, "limit": 50, "offset": 0}
        slots_resp = c.post(
            f"{base}/search_slots",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        slots_json = {}
        try:
            slots_json = slots_resp.json()
        except Exception:
            return {"flow": "doctors", "status": "failed", "error": f"search_slots http {slots_resp.status_code}"}
        slots = slots_json.get("slots", [])
        if not slots:
            return {"flow": "doctors", "status": "no_slots"}
        slot_id = slots[0]["slot_id"]
        r = c.post(f"{base}/appointments", headers=_h(base, tok), json={"slot_id": slot_id})
        if r.status_code >= 400:
            return {"flow": "doctors", "status": "failed", "error": r.text}
        ap = r.json()
        return {"flow": "doctors", "status": "ok", "appointment_id": ap.get("id"), "payment_request_id": ap.get("payment_request_id")}


def main():
    phone = os.getenv("PHONE_A", "+963900000001")
    name = os.getenv("NAME_A", "Alice")
    run = os.getenv("FLOWS", "commerce").split(",")

    results = []
    if "commerce" in run:
        base = os.getenv("COMMERCE_BASE_URL", "http://localhost:8083")
        try:
            results.append(flow_commerce_checkout(base, phone, name))
        except Exception as e:
            results.append({"flow": "commerce", "status": "error", "error": str(e)})
    if "doctors" in run:
        base = os.getenv("DOCTORS_BASE_URL", "http://localhost:8086")
        try:
            results.append(flow_doctors_appointment(base, phone, name))
        except Exception as e:
            results.append({"flow": "doctors", "status": "error", "error": str(e)})

    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
