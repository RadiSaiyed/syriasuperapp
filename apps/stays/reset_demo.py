"""
Reset (drop+create) the Stays schema for local development.

WARNING: This drops all tables in the Stays service schema (data loss).

Usage (from repo root):
  DB_URL=postgresql+psycopg2://postgres:postgres@localhost:5441/stays \
  python apps/stays/reset_demo.py
"""
from __future__ import annotations

import os

try:
    from app.database import SessionLocal
    from app.models import Base
except ModuleNotFoundError:
    from apps.stays.app.database import SessionLocal  # type: ignore
    from apps.stays.app.models import Base  # type: ignore


def main():
    print("Resetting Stays schema (drop_all + create_all)…")
    with SessionLocal() as session:
        bind = session.bind
        assert bind is not None
        Base.metadata.drop_all(bind=bind)
        Base.metadata.create_all(bind=bind)
    print("Done.")


if __name__ == "__main__":
    if not os.getenv("DB_URL"):
        os.environ["DB_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5441/stays"
    main()

