from __future__ import annotations

from .celery_app import celery_app
from .database import SessionLocal
from .routers import webhooks as webhooks_router


@celery_app.task(name="app.tasks.process_webhook_batch")
def process_webhook_batch(limit: int = 50) -> int:
    """Process pending webhook deliveries in a batch.
    Returns number of deliveries attempted (best-effort approximation).
    """
    count = 0
    db = SessionLocal()
    try:
        # _process_once internally limits and updates records
        webhooks_router._process_once(db, limit=limit)  # type: ignore[attr-defined]
        # We approximate by returning the requested limit; accurate counting would require model reads.
        count = limit
        return count
    except Exception:
        # Do not crash worker; rely on retry/backoff at application level for webhooks
        return 0
    finally:
        db.close()

