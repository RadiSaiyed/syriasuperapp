import os
from celery import Celery
from datetime import timedelta


broker = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "payments",
    broker=broker,
    backend=os.getenv("CELERY_RESULT_BACKEND", broker),
    include=["app.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    task_default_queue="payments",
    task_acks_late=True,
)

# Optional periodic schedule for webhook processing
try:
    interval = int(os.getenv("WEBHOOK_PROCESS_INTERVAL_SECS", "0"))
except Exception:
    interval = 0

if interval > 0:
    celery_app.conf.beat_schedule = {
        "process-webhooks": {
            "task": "app.tasks.process_webhook_batch",
            "schedule": timedelta(seconds=interval),
            "args": [50],
        }
    }

