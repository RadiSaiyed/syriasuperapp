#!/usr/bin/env python3
"""
Scaffold Alembic migration templates for apps/* services.

Creates (if missing):
- apps/<app>/alembic.ini
- apps/<app>/alembic/env.py
- apps/<app>/alembic/script.py.mako
- apps/<app>/alembic/README

Usage:
  python3 tools/scaffold_alembic.py            # all apps with app/models.py
  python3 tools/scaffold_alembic.py --apps commerce,food
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"

ALEMBIC_INI = """[alembic]
script_location = alembic
sqlalchemy.url = %(DB_URL)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

ENV_PY = """import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
from pathlib import Path


config = context.config

db_url = os.getenv("DB_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

SCRIPT_MAKO = """\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else 'pass'}


def downgrade() -> None:
    ${downgrades if downgrades else 'pass'}
"""

README_TMPL = """Use Alembic from this directory.

Commands
- Generate initial migration (autogenerate):
  DB_URL={db_url} alembic revision --autogenerate -m "init"
- Apply to head:
  DB_URL={db_url} alembic upgrade head

Notes
- env.py targets `app.models.Base` for autogenerate. Review diffs before applying.
"""


def detect_default_db_url(app_dir: Path, app_name: str) -> str:
    cfg = app_dir / "app" / "config.py"
    if cfg.exists():
        txt = cfg.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"DB_URL\s*:\s*str\s*=\s*os\.getenv\([^,]+,\s*\"([^\"]+)\"\)", txt)
        if m:
            return m.group(1)
    # generic fallback
    return f"postgresql+psycopg2://postgres:postgres@localhost:5432/{app_name}"


def scaffold_for(app_name: str) -> bool:
    app_dir = APPS / app_name
    if not (app_dir / "app" / "models.py").exists():
        return False
    if (app_dir / "alembic.ini").exists():
        return False

    db_url = detect_default_db_url(app_dir, app_name)
    alembic_dir = app_dir / "alembic"
    alembic_dir.mkdir(parents=True, exist_ok=True)

    (app_dir / "alembic.ini").write_text(ALEMBIC_INI, encoding="utf-8")
    (alembic_dir / "env.py").write_text(ENV_PY, encoding="utf-8")
    (alembic_dir / "script.py.mako").write_text(SCRIPT_MAKO, encoding="utf-8")
    (alembic_dir / "README").write_text(README_TMPL.format(db_url=db_url), encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", help="Comma-separated list of apps to scaffold; default=all with models", default="")
    args = ap.parse_args()

    if args.apps:
        apps = [a.strip() for a in args.apps.split(",") if a.strip()]
    else:
        apps = [p.name for p in sorted(APPS.iterdir()) if (p / "app" / "models.py").exists()]

    created = []
    skipped = []
    for app in apps:
        ok = scaffold_for(app)
        (created if ok else skipped).append(app)

    print("[scaffold] created:", ", ".join([a for a in created]))
    print("[scaffold] skipped (no models or already exists):", ", ".join([a for a in skipped]))


if __name__ == "__main__":
    main()

