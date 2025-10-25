#!/usr/bin/env python3
"""
Production readiness audit for the Syria Super‑App monorepo.

Runs a lightweight, static inspection and reports critical gaps:
- Secrets hygiene (.env committed)
- DB schema strategy (alembic vs. create_all)
- Prod hardening guards in config
- Rate limiting backend enforcement
- Compose template flags for internal HMAC

Usage:
  python3 tools/prod_audit.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"


def read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def list_dirs(p: Path) -> Iterable[Path]:
    return [d for d in p.iterdir() if d.is_dir()]


def audit_app(app_dir: Path) -> dict:
    name = app_dir.name
    res = {
        "name": name,
        "dockerfile": (app_dir / "Dockerfile").exists(),
        "env_example": (app_dir / ".env.example").exists(),
        "env_present": (app_dir / ".env").exists(),
        "alembic": (app_dir / "alembic.ini").exists() and (app_dir / "alembic").exists(),
        "auto_create_in_main": False,
        "config_hardening_present": False,
        "requires_redis_rate_limit": False,
    }

    # Detect create_all usage
    main_py = app_dir / "app" / "main.py"
    if main_py.exists():
        txt = read_text_safe(main_py)
        res["auto_create_in_main"] = "Base.metadata.create_all" in txt

    # Config hardening heuristics
    cfg_py = app_dir / "app" / "config.py"
    if cfg_py.exists():
        cfg = read_text_safe(cfg_py)
        # Hardened prod block
        res["config_hardening_present"] = (
            "if not settings.DEV_MODE" in cfg or "when ENV!=dev" in cfg
        )
        # Some services enforce redis in prod explicitly
        res["requires_redis_rate_limit"] = (
            "RATE_LIMIT_BACKEND must be 'redis'" in cfg
            or re.search(r"RATE_LIMIT_BACKEND\s*:\s*str = os\.getenv\(.*'redis'\)\s*#?", cfg) is not None
        )

    return res


def main() -> int:
    print("[audit] Syria Super‑App — production readiness scan")
    print(f"[audit] Repo: {ROOT}")

    if not APPS_DIR.exists():
        print("[audit] apps/ directory not found", file=sys.stderr)
        return 2

    apps = sorted([d for d in list_dirs(APPS_DIR) if (d / "app").exists()])
    results = [audit_app(d) for d in apps]

    total_envs = sum(1 for d in apps if (d / ".env").exists())
    print("\n== Secrets hygiene ==")
    if total_envs:
        print(f"- Found {total_envs} committed .env files under apps/. Consider removing and relying on .env.example + external secret injection.")
    else:
        print("- OK: no committed .env files under apps/.")

    print("\n== App checks ==")
    for r in results:
        issues = []
        if not r["dockerfile"]:
            issues.append("no Dockerfile")
        if not r["env_example"]:
            issues.append("missing .env.example")
        if r["env_present"]:
            issues.append(".env committed")
        if r["auto_create_in_main"] and not r["alembic"]:
            issues.append("create_all without alembic (add migrations or pre-provision schema)")
        if not r["config_hardening_present"]:
            issues.append("missing prod hardening block in config.py")
        if "payments" not in r["name"] and not r["requires_redis_rate_limit"]:
            # Payments has its own Celery & rate limit paths; other services should enforce redis in prod
            issues.append("rate limiter not enforced to redis in prod")

        status = "OK" if not issues else ", ".join(issues)
        print(f"- {r['name']}: {status}")

    # Compose template flags
    compose = ROOT / "ops" / "deploy" / "compose-traefik" / "docker-compose.yml"
    if compose.exists():
        text = read_text_safe(compose)
        hmac_ok = "INTERNAL_REQUIRE_HMAC" in text
        print("\n== Deploy template (Traefik compose) ==")
        if hmac_ok:
            print("- OK: payments-api sets INTERNAL_REQUIRE_HMAC (internal HMAC enforced).")
        else:
            print("- Missing INTERNAL_REQUIRE_HMAC for payments-api. Set INTERNAL_REQUIRE_HMAC=true in payments env.")
    else:
        print("\n== Deploy template ==\n- ops/deploy/compose-traefik/docker-compose.yml not found")

    print("\n== Recommendations (P0) ==")
    print("- Remove committed .env files; keep only .env.example and load real secrets via CI/secrets manager.")
    print("- Add Alembic migrations for services that disable AUTO_CREATE_SCHEMA in prod.")
    print("- Enforce rate limiter backend 'redis' in prod across all services.")
    print("- Require INTERNAL_REQUIRE_HMAC=true for Payments internal endpoints and sign callers.")
    print("- Set explicit ALLOWED_ORIGINS for each API; no wildcard in prod.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

