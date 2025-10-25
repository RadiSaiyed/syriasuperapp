#!/usr/bin/env python3
"""
Generate ops/deploy/compose-traefik/.env.prod with strong secrets.

Usage examples:
  python3 tools/gen_prod_env.py --base-domain example.com --org myorg \
    --acme-email ops@example.com --out ops/deploy/compose-traefik/.env.prod

Notes:
  - Safe defaults are generated for all *_JWT_SECRET and *_ADMIN_TOKEN_SHA256 values.
  - ALLOWED_ORIGINS are derived from --base-domain.
  - Existing output is left untouched unless --force is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = ROOT / "ops" / "deploy" / "compose-traefik"


def rand_hex(n: int = 32) -> str:
    return secrets.token_hex(n)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-domain", default=os.getenv("BASE_DOMAIN", "example.com"))
    ap.add_argument("--org", default=os.getenv("ORG", "your_dockerhub_user"))
    ap.add_argument("--registry", default=os.getenv("REGISTRY", "docker.io"))
    ap.add_argument("--acme-email", default=os.getenv("TRAEFIK_ACME_EMAIL", "ops@example.com"))
    ap.add_argument("--tag", default=os.getenv("TAG", "latest"))
    ap.add_argument("--out", default=str(DEPLOY_DIR / ".env.prod"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not args.force:
        print(f"[gen] {out_path} already exists; use --force to overwrite.")
        return 0

    base = args.base_domain.strip()
    org = args.org.strip()
    reg = args.registry.strip()
    email = args.acme_email.strip()
    tag = args.tag.strip()

    # Derive CORS defaults
    common_allowed = f"https://*.{base}"
    payments_allowed = f"https://payments.{base}"
    taxi_allowed = f"https://taxi.{base}"

    # Admin tokens: generate a random plain token, and derive sha256 digest
    taxi_admin_token = secrets.token_urlsafe(24)
    taxi_admin_token_sha256 = sha256_hex(taxi_admin_token)
    payments_admin_token = secrets.token_urlsafe(24)
    payments_admin_token_sha256 = sha256_hex(payments_admin_token)

    # Build env body
    lines = []
    def add(k: str, v: str):
        lines.append(f"{k}={v}")

    add("REGISTRY", reg)
    add("ORG", org)
    add("TAG", tag)
    add("BASE_DOMAIN", base)
    add("TRAEFIK_ACME_EMAIL", email)
    # CORS
    add("COMMON_ALLOWED_ORIGINS", common_allowed)
    add("PAYMENTS_ALLOWED_ORIGINS", payments_allowed)
    add("TAXI_ALLOWED_ORIGINS", taxi_allowed)

    # Core secrets
    for svc in [
        "PAYMENTS", "TAXI", "AUTOMARKET", "BUS", "CHAT", "COMMERCE", "DOCTORS",
        "FOOD", "FREIGHT", "JOBS", "STAYS", "UTILITIES",
    ]:
        add(f"{svc}_JWT_SECRET", rand_hex(32))

    # Internal auth
    add("PAYMENTS_INTERNAL_SECRET", rand_hex(32))

    # Optional fee wallet placeholder
    add("FEE_WALLET_PHONE", "")

    # Taxi admin + reaper
    add("TAXI_ADMIN_TOKEN", taxi_admin_token)
    add("TAXI_ADMIN_TOKEN_SHA256", taxi_admin_token_sha256)
    add("TAXI_REAPER_INTERVAL_SECS", "60")
    add("TAXI_REAPER_TIMEOUT_SECS", "120")
    add("TAXI_REAPER_LIMIT", "200")
    add("TAXI_REAPER_RELAX_WALLET", "false")

    # Payments admin (no reaper, but admin endpoints protected)
    add("PAYMENTS_ADMIN_TOKEN_SHA256", payments_admin_token_sha256)

    # Maps API key placeholder for Taxi (Google Maps)
    add("GOOGLE_MAPS_API_KEY_TAXI", "")

    out = "\n".join(lines) + "\n"
    out_path.write_text(out, encoding="utf-8")
    print(f"[gen] Wrote {out_path} with strong defaults.")
    print("[gen] IMPORTANT: Set real values for ORG, BASE_DOMAIN, GOOGLE_MAPS_API_KEY_TAXI, and update allowed origins as needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
