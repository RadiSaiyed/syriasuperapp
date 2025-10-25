#!/usr/bin/env python3
"""
Sync secrets from ops/secrets/superapp.secrets.env into per‑app .env files.

Usage:
  python3 tools/sync_secrets.py [--secrets ops/secrets/superapp.secrets.env] [--apps payments,bus,...] [--dry-run]

Notes:
  - Creates apps/<app>/.env if missing (copies from .env.example when available).
  - Idempotent: updates existing keys, appends missing ones.
  - Only writes known secret keys; other variables are left untouched.
"""

from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRETS = REPO_ROOT / "ops" / "secrets" / "superapp.secrets.env"


def load_secrets(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def ensure_env_file(app_dir: Path) -> Path:
    env_file = app_dir / ".env"
    if env_file.exists():
        return env_file
    example = app_dir / ".env.example"
    if example.exists():
        env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        env_file.write_text("", encoding="utf-8")
    return env_file


def parse_env_file(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []


def write_env_file(path: Path, lines: List[str]) -> None:
    text = "\n".join(lines).rstrip("\n") + "\n"
    path.write_text(text, encoding="utf-8")


def upsert_env_vars(lines: List[str], updates: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
    """Return new lines and a dict of actually-updated keys->value.
    Preserves comments/unknown lines; updates existing key lines of form KEY=...
    """
    existing_positions: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k = s.split("=", 1)[0].strip()
        if k:
            existing_positions[k] = idx

    changed: Dict[str, str] = {}
    out = list(lines)
    for key, val in updates.items():
        if key in existing_positions:
            i = existing_positions[key]
            before = out[i]
            new_line = f"{key}={val}"
            if before.strip() != new_line:
                out[i] = new_line
                changed[key] = val
        else:
            out.append(f"{key}={val}")
            changed[key] = val
    return out, changed


def build_app_secret_map(app: str, secrets: Dict[str, str]) -> Dict[str, str]:
    APP = app.upper()
    out: Dict[str, str] = {}
    # Common
    jwt = secrets.get(f"{APP}_JWT_SECRET")
    if jwt:
        out["JWT_SECRET"] = jwt

    # Payments
    if app == "payments":
        s1 = secrets.get("PAYMENTS_INTERNAL_API_SECRET") or secrets.get("INTERNAL_API_SECRET")
        if s1:
            out["INTERNAL_API_SECRET"] = s1
        adm = secrets.get("PAYMENTS_ADMIN_TOKEN")
        if adm:
            out["ADMIN_TOKEN"] = adm
        return out

    # Verticals with Payments integration
    if app in {"bus", "taxi", "commerce", "utilities", "freight", "automarket", "stays", "doctors", "food", "flights"}:
        s2 = secrets.get(f"{APP}_PAYMENTS_INTERNAL_SECRET") or secrets.get("INTERNAL_API_SECRET")
        if s2:
            out["PAYMENTS_INTERNAL_SECRET"] = s2

    # Webhook consumers
    if app in {"stays", "doctors", "food"}:
        wh = secrets.get(f"{APP}_PAYMENTS_WEBHOOK_SECRET")
        if wh:
            out["PAYMENTS_WEBHOOK_SECRET"] = wh

    # Ops Admin (special path/apps name)
    if app == "ops_admin":
        u = secrets.get("OPS_ADMIN_BASIC_USER")
        p = secrets.get("OPS_ADMIN_BASIC_PASS")
        if u:
            out["OPS_ADMIN_BASIC_USER"] = u
        if p:
            out["OPS_ADMIN_BASIC_PASS"] = p

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secrets", type=str, default=str(DEFAULT_SECRETS), help="Path to superapp.secrets.env")
    ap.add_argument("--apps", type=str, default="", help="Comma-separated list of apps to update (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write files; just print planned changes")
    args = ap.parse_args()

    secrets_path = Path(args.secrets)
    if not secrets_path.exists():
        raise SystemExit(f"Secrets file not found: {secrets_path}")
    secrets = load_secrets(secrets_path)

    apps_dir = REPO_ROOT / "apps"
    all_apps = sorted([p.name for p in apps_dir.iterdir() if p.is_dir()])
    target_apps = [a.strip() for a in args.apps.split(",") if a.strip()] if args.apps else all_apps

    wrote_any = False
    for app in target_apps:
        app_dir = apps_dir / app
        if not app_dir.exists():
            print(f"[skip] {app}: not found")
            continue
        # Special case: ops_admin lives in apps/ops_admin but uses custom keys
        secrets_map = build_app_secret_map("ops_admin" if app == "ops_admin" else app, secrets)
        if not secrets_map:
            print(f"[skip] {app}: no matching secrets in {secrets_path.name}")
            continue

        env_file = ensure_env_file(app_dir)
        orig_lines = parse_env_file(env_file)
        new_lines, changed = upsert_env_vars(orig_lines, secrets_map)
        if not changed:
            print(f"[ok]   {app}: up to date ({env_file})")
            continue
        if args.dry_run:
            print(f"[plan] {app}: would update {env_file}")
            for k, v in changed.items():
                print(f"       - {k}={v}")
            continue
        write_env_file(env_file, new_lines)
        wrote_any = True
        print(f"[done] {app}: updated {env_file}")
        for k, v in changed.items():
            print(f"       - {k}={v}")

    if not wrote_any and not args.dry_run:
        print("No changes were necessary.")


if __name__ == "__main__":
    main()

