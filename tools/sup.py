#!/usr/bin/env python3
"""
sup — Single‑Operator helper CLI for the Super‑App monorepo

Goals:
- Give one person a unified entrypoint for common ops:
  - bootstrap (secrets → envs, start core stack)
  - up/down/logs/ps for any app (docker compose)
  - observability up/down/logs
  - doctor: run repo health checks and tests smoke
  - deploy (compose‑traefik) up/down/restart wrappers
  - backup (payments DB)
  - runbooks/links quick access

Usage examples:
  python3 tools/sup.py help
  python3 tools/sup.py bootstrap
  python3 tools/sup.py up payments
  python3 tools/sup.py logs payments
  python3 tools/sup.py obs up
  python3 tools/sup.py doctor
  python3 tools/sup.py deploy up
  python3 tools/sup.py backup payments --out ./backups

This CLI wraps existing repo scripts to reduce toil and memory overhead.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"
OBS_DIR = ROOT / "ops" / "observability"
OPERATORS_DIR = ROOT / "operators"
DEPLOY_DIR = ROOT / "ops" / "deploy" / "compose-traefik"


def sh(cmd: List[str], cwd: Path | None = None, check: bool = True) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check).returncode


def shell_out(cmd: str, cwd: Path | None = None, check: bool = True) -> int:
    print(f"$ bash -lc {cmd!r}")
    return subprocess.run(["bash", "-lc", cmd], cwd=str(cwd) if cwd else None, check=check).returncode


def list_apps() -> List[str]:
    out: List[str] = []
    if not APPS_DIR.exists():
        return out
    for d in sorted(APPS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / "docker-compose.yml").exists():
            out.append(d.name)
    return out


def ensure_docker():
    if shutil.which("docker") is None:
        raise SystemExit("Docker is required for this command. Install Docker and retry.")


def cmd_help(_: argparse.Namespace) -> int:
    print(
        """
sup — Single‑Operator helper

Commands
  help                     Show this help
  apps                     List available apps (compose‑enabled)
  bootstrap                Sync secrets and start core stack (payments + observability)

  up <app>                 docker compose up -d in apps/<app>
  down <app>               docker compose down in apps/<app>
  logs <app>               docker compose logs -f in apps/<app>
  ps <app>                 docker compose ps in apps/<app>

  obs up|down|logs|ps      Manage local observability stack
  doctor                   Run repo health check (tools/health_check.sh)
  deploy up|down|restart   Wrap ops/deploy/compose-traefik (requires .env.prod)
  backup payments [--out DIR]  Run Postgres backup for Payments
  runbook <topic>          Print path to a runbook
                           Topics: payments | operators-ui | taxi-webhooks
  stack up|down|list [preset]  Presets: core (obs+payments), all
  op list                 List operator services under operators/
  op up|down|logs|ps <name>    Manage operator services under operators/<name>
  seed <target> [--base URL]   Seed demo data; targets: food, food-operator, stays, commerce, doctors, doctors-webhooks, doctors-payments, commerce-webhooks, taxi, bus, utilities, freight, carmarket, chat
                               [--db URL] for DB seeding (stays)
        """
    )
    return 0


def cmd_apps(_: argparse.Namespace) -> int:
    apps = list_apps()
    if not apps:
        print("No apps with docker-compose.yml found under apps/.")
        return 1
    for a in apps:
        print(a)
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    ensure_docker()
    app = args.app
    app_dir = APPS_DIR / app
    if not (app_dir / "docker-compose.yml").exists():
        raise SystemExit(f"No docker-compose.yml in {app_dir}")
    return sh(["docker", "compose", "up", "-d"], cwd=app_dir)


def cmd_down(args: argparse.Namespace) -> int:
    ensure_docker()
    app_dir = APPS_DIR / args.app
    if not (app_dir / "docker-compose.yml").exists():
        raise SystemExit(f"No docker-compose.yml in {app_dir}")
    return sh(["docker", "compose", "down"], cwd=app_dir)


def cmd_logs(args: argparse.Namespace) -> int:
    ensure_docker()
    app_dir = APPS_DIR / args.app
    if not (app_dir / "docker-compose.yml").exists():
        raise SystemExit(f"No docker-compose.yml in {app_dir}")
    return sh(["docker", "compose", "logs", "-f", "--tail=200"], cwd=app_dir)


def cmd_ps(args: argparse.Namespace) -> int:
    ensure_docker()
    app_dir = APPS_DIR / args.app
    if not (app_dir / "docker-compose.yml").exists():
        raise SystemExit(f"No docker-compose.yml in {app_dir}")
    return sh(["docker", "compose", "ps"], cwd=app_dir)


def cmd_obs(args: argparse.Namespace) -> int:
    ensure_docker()
    dc = OBS_DIR / "docker-compose.yml"
    if not dc.exists():
        raise SystemExit(f"Missing observability compose: {dc}")
    op = args.action
    if op == "up":
        return sh(["docker", "compose", "-f", str(dc), "up", "-d"], cwd=OBS_DIR)
    if op == "down":
        return sh(["docker", "compose", "-f", str(dc), "down"], cwd=OBS_DIR)
    if op == "logs":
        return sh(["docker", "compose", "-f", str(dc), "logs", "-f", "--tail=200"], cwd=OBS_DIR)
    if op == "ps":
        return sh(["docker", "compose", "-f", str(dc), "ps"], cwd=OBS_DIR)
    raise SystemExit("obs requires one of: up, down, logs, ps")


def cmd_doctor(_: argparse.Namespace) -> int:
    script = ROOT / "tools" / "health_check.sh"
    if not script.exists():
        raise SystemExit(f"Not found: {script}")
    return shell_out(f"bash {script}")


def cmd_bootstrap(_: argparse.Namespace) -> int:
    # 1) Sync secrets to .env files
    secrets_sync = ROOT / "tools" / "sync_secrets.py"
    if secrets_sync.exists():
        print("[sup] Syncing secrets to per‑app .env files…")
        rc = sh([sys.executable, str(secrets_sync)])
        if rc != 0:
            return rc
    else:
        print("[sup] Skipping secrets sync (tools/sync_secrets.py missing)")

    # 2) Bring up observability (Prometheus + Grafana + Alertmanager)
    print("[sup] Starting observability stack…")
    rc = cmd_obs(argparse.Namespace(action="up"))
    if rc != 0:
        return rc

    # 3) Bring up Payments (db, redis, api)
    print("[sup] Starting core service: payments…")
    rc = cmd_up(argparse.Namespace(app="payments"))
    if rc != 0:
        return rc

    print("[sup] Bootstrap complete. URLs:")
    print("- Payments API: http://localhost:8080/docs")
    print("- Grafana:      http://localhost:3000 (default anonymous, see ops/observability)")
    print("- Prometheus:   http://localhost:9090")
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    ensure_docker()
    if not (DEPLOY_DIR / "docker-compose.yml").exists():
        raise SystemExit(f"Missing deploy compose: {DEPLOY_DIR}/docker-compose.yml")
    env_file = DEPLOY_DIR / ".env.prod"
    if not env_file.exists():
        print(f"[warn] {env_file} not found. Copy .env.prod.example → .env.prod and adjust.")
    action = args.action
    if action == "up":
        return sh(["docker", "compose", "--env-file", str(env_file), "-f", "docker-compose.yml", "up", "-d"], cwd=DEPLOY_DIR)
    if action == "down":
        return sh(["docker", "compose", "--env-file", str(env_file), "-f", "docker-compose.yml", "down", "-v"], cwd=DEPLOY_DIR)
    if action == "restart":
        rc = sh(["docker", "compose", "--env-file", str(env_file), "-f", "docker-compose.yml", "down"], cwd=DEPLOY_DIR)
        if rc != 0:
            return rc
        return sh(["docker", "compose", "--env-file", str(env_file), "-f", "docker-compose.yml", "up", "-d"], cwd=DEPLOY_DIR)
    raise SystemExit("deploy requires one of: up, down, restart")


def cmd_backup(args: argparse.Namespace) -> int:
    if args.app != "payments":
        raise SystemExit("Only payments backup is supported for now.")
    script = ROOT / "ops" / "backups" / "payments_pg_backup.sh"
    if not script.exists():
        raise SystemExit(f"Missing backup script: {script}")
    out_dir = Path(args.out).resolve() if args.out else (ROOT / "ops" / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Default to local dev DB unless user overrides DB_URL
    env.setdefault("DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5433/payments")
    env["OUT_DIR"] = str(out_dir)
    print(f"[sup] Writing backups under {out_dir}")
    return subprocess.run(["bash", str(script)], env=env, check=False).returncode


def cmd_runbook(args: argparse.Namespace) -> int:
    topic = args.topic
    if topic == "payments":
        p = ROOT / "ops" / "runbooks" / "payments.md"
        print(p)
        return 0 if p.exists() else 1
    if topic in ("operators-ui", "operators_ui"):
        p = ROOT / "ops" / "runbooks" / "operators_ui.md"
        print(p)
        return 0 if p.exists() else 1
    if topic in ("taxi-webhooks", "taxi_webhooks"):
        p = ROOT / "ops" / "runbooks" / "taxi_webhooks_sim.md"
        print(p)
        return 0 if p.exists() else 1
    print("Unknown runbook topic. Try: payments, operators-ui, taxi-webhooks")
    return 1

# --- Stacks (presets) ---
STACKS = {
    "core": ["payments"],  # observability handled explicitly
    "all": None,  # special: all compose-enabled apps
    # Extended presets
    "food-operator": ["food"],  # plus operators/food_operator
}


def cmd_stack(args: argparse.Namespace) -> int:
    action = args.action
    preset = args.preset
    if action == "list":
        print("Presets: core, all, food-operator")
        print("- core: observability + payments")
        print("- all:  every compose-enabled app (no observability)")
        print("- food-operator: apps/food + operators/food_operator")
        return 0
    if preset not in STACKS:
        raise SystemExit("Unknown preset. Use: core, all, or run 'sup stack list'.")
    if preset == "core":
        if action == "up":
            rc = cmd_obs(argparse.Namespace(action="up"))
            if rc != 0:
                return rc
            for app in STACKS["core"]:
                rc = cmd_up(argparse.Namespace(app=app))
                if rc != 0:
                    return rc
            print("[sup] core stack up: observability + payments ready")
            return 0
        else:
            for app in reversed(STACKS["core"]):
                cmd_down(argparse.Namespace(app=app))
            cmd_obs(argparse.Namespace(action="down"))
            print("[sup] core stack down")
            return 0
    elif preset == "food-operator":
        # apps/food + operators/food_operator
        if action == "up":
            rc = cmd_up(argparse.Namespace(app="food"))
            if rc != 0:
                return rc
            rc = cmd_op(argparse.Namespace(action="up", name="food_operator"))
            if rc != 0:
                return rc
            print("[sup] food-operator stack up: food + food_operator ready")
            return 0
        else:
            cmd_op(argparse.Namespace(action="down", name="food_operator"))
            cmd_down(argparse.Namespace(app="food"))
            print("[sup] food-operator stack down")
            return 0
    # all
    apps = list_apps()
    if action == "up":
        for a in apps:
            rc = cmd_up(argparse.Namespace(app=a))
            if rc != 0:
                return rc
        print("[sup] all stack up: started all apps")
    else:
        for a in reversed(apps):
            cmd_down(argparse.Namespace(app=a))
        print("[sup] all stack down: stopped all apps")
    return 0

    # Extended presets (handled above return? safeguard)



def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(add_help=False)
    sp = ap.add_subparsers(dest="cmd")

    sp.add_parser("help")
    sp.add_parser("apps")

    sp.add_parser("bootstrap")

    p_up = sp.add_parser("up"); p_up.add_argument("app")
    p_down = sp.add_parser("down"); p_down.add_argument("app")
    p_logs = sp.add_parser("logs"); p_logs.add_argument("app")
    p_ps = sp.add_parser("ps"); p_ps.add_argument("app")

    p_obs = sp.add_parser("obs"); p_obs.add_argument("action", choices=["up", "down", "logs", "ps"])

    sp.add_parser("doctor")

    p_deploy = sp.add_parser("deploy"); p_deploy.add_argument("action", choices=["up", "down", "restart"])

    p_backup = sp.add_parser("backup"); p_backup.add_argument("app"); p_backup.add_argument("--out", default="")

    p_rb = sp.add_parser("runbook"); p_rb.add_argument("topic")

    # Stack presets
    p_stack = sp.add_parser("stack")
    p_stack.add_argument("action", choices=["up", "down", "list"])
    p_stack.add_argument("preset", nargs="?", default="core")

    # Operators
    p_op = sp.add_parser("op")
    p_op.add_argument("action", choices=["up", "down", "logs", "ps", "list"])
    p_op.add_argument("name", nargs="?")

    # Seed
    p_seed = sp.add_parser("seed")
    p_seed.add_argument("target", choices=["food", "food-operator", "stays", "commerce", "doctors", "doctors-webhooks", "doctors-payments", "commerce-webhooks", "taxi", "bus", "utilities", "freight", "carmarket", "chat"])
    p_seed.add_argument("--base", dest="base", default="", help="Override base URL (for HTTP seeds)")
    p_seed.add_argument("--db", dest="db", default="", help="Override DB_URL (for DB seeds like stays)")

    return ap


def main() -> int:
    ap = build_parser()
    ns = ap.parse_args()
    cmd = ns.cmd or "help"
    if cmd == "help":
        return cmd_help(ns)
    if cmd == "apps":
        return cmd_apps(ns)
    if cmd == "bootstrap":
        return cmd_bootstrap(ns)
    if cmd == "up":
        return cmd_up(ns)
    if cmd == "down":
        return cmd_down(ns)
    if cmd == "logs":
        return cmd_logs(ns)
    if cmd == "ps":
        return cmd_ps(ns)
    if cmd == "obs":
        return cmd_obs(ns)
    if cmd == "doctor":
        return cmd_doctor(ns)
    if cmd == "deploy":
        return cmd_deploy(ns)
    if cmd == "backup":
        return cmd_backup(ns)
    if cmd == "runbook":
        return cmd_runbook(ns)
    if cmd == "stack":
        return cmd_stack(ns)
    if cmd == "op":
        return cmd_op(ns)
    if cmd == "seed":
        return cmd_seed(ns)
    return cmd_help(ns)

def _op_dir(name: str) -> Path:
    return OPERATORS_DIR / name


def cmd_op(args: argparse.Namespace) -> int:
    ensure_docker()
    action = args.action
    if action == "list":
        # List operator services that have docker-compose.yml
        names = []
        if OPERATORS_DIR.exists():
            for d in sorted(OPERATORS_DIR.iterdir()):
                if d.is_dir() and (d / "docker-compose.yml").exists():
                    names.append(d.name)
        for n in names:
            print(n)
        return 0
    name = args.name
    op_dir = _op_dir(name)
    if not (op_dir / "docker-compose.yml").exists():
        raise SystemExit(f"No docker-compose.yml in {op_dir}")
    if action == "up":
        return sh(["docker", "compose", "up", "-d"], cwd=op_dir)
    if action == "down":
        return sh(["docker", "compose", "down"], cwd=op_dir)
    if action == "logs":
        return sh(["docker", "compose", "logs", "-f", "--tail=200"], cwd=op_dir)
    if action == "ps":
        return sh(["docker", "compose", "ps"], cwd=op_dir)
    return 0


def _run_seed_food(base: str | None = None) -> int:
    script = ROOT / "tools" / "seed" / "seed_food_demo.sh"
    if not script.exists():
        print(f"[seed] missing script: {script}")
        return 1
    env = os.environ.copy()
    if base:
        env["FOOD_BASE"] = base
    print(f"[seed] FOOD_BASE={env.get('FOOD_BASE', 'http://localhost:8090')}")
    return subprocess.run(["bash", str(script)], env=env, check=False).returncode


def cmd_seed(args: argparse.Namespace) -> int:
    target = args.target
    base = (args.base or "").strip() or None
    if target == "food":
        print("[seed] Ensuring Food API is up…")
        rc = cmd_up(argparse.Namespace(app="food"))
        if rc != 0:
            return rc
        return _run_seed_food(base)
    if target == "food-operator":
        print("[seed] Ensuring Food + Operator stack is up…")
        rc = cmd_stack(argparse.Namespace(action="up", preset="food-operator"))
        if rc != 0:
            return rc
        return _run_seed_food(base)
    if target == "stays":
        print("[seed] Ensuring Stays API is up…")
        rc = cmd_up(argparse.Namespace(app="stays"))
        if rc != 0:
            return rc
        # Run python seed script with DB_URL default or override
        db_url = (args.db or os.environ.get("STAYS_DB_URL") or "postgresql+psycopg2://postgres:postgres@localhost:5441/stays").strip()
        env = os.environ.copy()
        env["DB_URL"] = db_url
        # Ensure PYTHONPATH includes app for relative imports
        pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{ROOT / 'apps' / 'stays'}" + (f":{pp}" if pp else "")
        print(f"[seed] DB_URL={db_url}")
        return subprocess.run([sys.executable, str(ROOT / 'apps' / 'stays' / 'seed_demo.py')], env=env, check=False).returncode
    if target == "commerce":
        print("[seed] Ensuring Commerce API is up…")
        rc = cmd_up(argparse.Namespace(app="commerce"))
        if rc != 0:
            return rc
        # Run HTTP seeder
        script = ROOT / "tools" / "seed" / "seed_commerce_demo.sh"
        env = os.environ.copy()
        if base:
            env["COMMERCE_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "doctors":
        print("[seed] Ensuring Doctors API is up…")
        rc = cmd_up(argparse.Namespace(app="doctors"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_doctors_demo.sh"
        env = os.environ.copy()
        if base:
            env["DOCTORS_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "doctors-webhooks":
        print("[seed] Ensuring Payments + Doctors are up…")
        rc = cmd_up(argparse.Namespace(app="payments"))
        if rc != 0:
            return rc
        rc = cmd_up(argparse.Namespace(app="doctors"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_doctors_webhooks_demo.sh"
        env = os.environ.copy()
        if base:
            env["DOCTORS_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "doctors-payments":
        print("[seed] Ensuring Payments + Doctors are up…")
        rc = cmd_up(argparse.Namespace(app="payments"))
        if rc != 0:
            return rc
        rc = cmd_up(argparse.Namespace(app="doctors"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_doctors_payments_flow.sh"
        env = os.environ.copy()
        if base:
            env["DOCTORS_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "taxi":
        print("[seed] Ensuring Taxi + Payments are up…")
        rc = cmd_up(argparse.Namespace(app="payments"))
        if rc != 0:
            return rc
        rc = cmd_up(argparse.Namespace(app="taxi"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "dev" / "seed_taxi_test.sh"
        env = os.environ.copy()
        if base:
            env["TAXI_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "bus":
        print("[seed] Ensuring Bus API is up…")
        rc = cmd_up(argparse.Namespace(app="bus"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_bus_demo.sh"
        env = os.environ.copy()
        if base:
            env["BUS_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "utilities":
        print("[seed] Ensuring Utilities API is up…")
        rc = cmd_up(argparse.Namespace(app="utilities"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_utilities_demo.sh"
        env = os.environ.copy()
        if base:
            env["UTIL_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "freight":
        print("[seed] Ensuring Freight API is up…")
        rc = cmd_up(argparse.Namespace(app="freight"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_freight_demo.sh"
        env = os.environ.copy()
        if base:
            env["FREIGHT_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "carmarket":
        print("[seed] Ensuring Car Market API is up…")
        rc = cmd_up(argparse.Namespace(app="carmarket"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_carmarket_demo.sh"
        env = os.environ.copy()
        if base:
            env["CARMARKET_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "chat":
        print("[seed] Ensuring Chat API is up…")
        rc = cmd_up(argparse.Namespace(app="chat"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_chat_demo.sh"
        env = os.environ.copy()
        if base:
            env["CHAT_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    if target == "commerce-webhooks":
        print("[seed] Ensuring Payments is up…")
        rc = cmd_up(argparse.Namespace(app="payments"))
        if rc != 0:
            return rc
        script = ROOT / "tools" / "seed" / "seed_payments_webhooks_demo.sh"
        env = os.environ.copy()
        if base:
            env["PAY_BASE"] = base
        return subprocess.run(["bash", str(script)], env=env, check=False).returncode
    print("[seed] unknown target")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
