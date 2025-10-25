#!/usr/bin/env python3
"""
Requeue failed or pending webhook deliveries for retry.

Usage:
  DB_URL=postgresql+psycopg2://... python apps/payments/scripts/webhooks_requeue.py [--endpoint-id UUID] [--status failed|pending]

Sets status to 'pending', resets attempt_count and clears last_error/next_attempt_at.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.models import WebhookDelivery  # type: ignore  # noqa: E402


def main() -> int:
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("Set DB_URL env to point to the payments database", file=sys.stderr)
        return 2
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint-id", help="UUID of webhook endpoint to filter")
    ap.add_argument("--status", default="failed", choices=["failed", "pending"], help="Source status to requeue")
    args = ap.parse_args()

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        q = session.query(WebhookDelivery).filter(WebhookDelivery.status == args.status)
        if args.endpoint_id:
            q = q.filter(WebhookDelivery.endpoint_id == args.endpoint_id)
        count = 0
        now = datetime.utcnow()
        for d in q.all():
            d.status = "pending"
            d.attempt_count = 0
            d.last_error = None
            d.last_attempt_at = None
            d.next_attempt_at = None
            count += 1
        session.commit()
        print(f"Requeued {count} deliveries from status '{args.status}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

