#!/usr/bin/env python3
import os
import sys
import json
import time
import httpx


BASE = os.getenv("PAYMENTS_BASE_URL", "http://localhost:8080")
TOKEN = os.getenv("PAYMENTS_MERCHANT_TOKEN", "")


def _h():
    if not TOKEN:
        print("Set PAYMENTS_MERCHANT_TOKEN to a valid Bearer token", file=sys.stderr)
        sys.exit(2)
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def create_qr(amount_cents: int):
    with httpx.Client(timeout=5.0) as c:
        r = c.post(f"{BASE}/payments/merchant/qr", headers=_h(), json={"amount_cents": amount_cents})
        r.raise_for_status()
        js = r.json()
        print(json.dumps(js))


def qr_status(code: str):
    with httpx.Client(timeout=5.0) as c:
        r = c.get(f"{BASE}/payments/merchant/qr_status", headers=_h(), params={"code": code})
        r.raise_for_status()
        print(json.dumps(r.json()))


def wait_paid(code: str, timeout_secs: int = 120):
    deadline = time.time() + timeout_secs
    with httpx.Client(timeout=5.0) as c:
        while time.time() < deadline:
            r = c.get(f"{BASE}/payments/merchant/qr_status", headers=_h(), params={"code": code})
            if r.status_code == 200:
                st = r.json().get("status")
                print(f"status={st}")
                if st in ("used", "expired"):
                    return
            time.sleep(2)
        print("timeout", file=sys.stderr)
        sys.exit(1)


def cpm_request(scanned_text: str, amount_cents: int):
    with httpx.Client(timeout=5.0) as c:
        r = c.post(f"{BASE}/payments/merchant/cpm_request", headers=_h(), json={"code": scanned_text, "amount_cents": amount_cents})
        r.raise_for_status()
        print(json.dumps(r.json()))


def help():
    print(
        "Usage:\n"
        "  pos_cli.py create_qr <amount_cents>\n"
        "  pos_cli.py qr_status <code>\n"
        "  pos_cli.py wait_paid <code> [timeout_secs]\n"
        "  pos_cli.py cpm_request <scanned_text> <amount_cents>\n"
        "Env: PAYMENTS_BASE_URL (default http://localhost:8080), PAYMENTS_MERCHANT_TOKEN (Bearer)"
    )


def main():
    if len(sys.argv) < 2:
        help(); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "create_qr" and len(sys.argv) == 3:
        create_qr(int(sys.argv[2])); return
    if cmd == "qr_status" and len(sys.argv) == 3:
        qr_status(sys.argv[2]); return
    if cmd == "wait_paid" and len(sys.argv) in (3,4):
        t = int(sys.argv[3]) if len(sys.argv)==4 else 120
        wait_paid(sys.argv[2], t); return
    if cmd == "cpm_request" and len(sys.argv) == 4:
        cpm_request(sys.argv[2], int(sys.argv[3])); return
    help(); sys.exit(1)


if __name__ == "__main__":
    main()

