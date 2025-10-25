import os
import json
from typing import Dict, Any


SINK = os.getenv("EVENT_SINK", "log").lower()  # log|none|kafka|nats


def publish(event_type: str, payload: Dict[str, Any]) -> None:
    if SINK == "none":
        return
    if SINK == "log":
        print(json.dumps({"type": event_type, "data": payload}))
        return
    # Future: implement Kafka/NATS here when libs/endpoints configured.
    # For now, gracefully fallback to log
    print(json.dumps({"type": event_type, "data": payload}))

