from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict
from prometheus_client import Counter
from .config import settings


PAY_INT_CALLS = Counter(
    "taxi_payments_internal_calls_total",
    "Payments internal calls",
    ["op", "result"],  # result: ok|err|skipped_cb_open
)


class _CBState:
    def __init__(self) -> None:
        self.fails: int = 0
        self.open_until: datetime | None = None


_STATES: Dict[str, _CBState] = {}


def _get(op: str) -> _CBState:
    s = _STATES.get(op)
    if s is None:
        s = _CBState()
        _STATES[op] = s
    return s


def allowed(op: str) -> bool:
    if not settings.PAYMENTS_CB_ENABLED:
        return True
    st = _get(op)
    if st.open_until and datetime.now(timezone.utc) < st.open_until:
        try:
            PAY_INT_CALLS.labels(op, "skipped_cb_open").inc()
        except Exception:
            pass
        return False
    return True


def record(op: str, ok: bool) -> None:
    st = _get(op)
    if ok:
        st.fails = 0
        st.open_until = None
        try:
            PAY_INT_CALLS.labels(op, "ok").inc()
        except Exception:
            pass
    else:
        st.fails += 1
        try:
            PAY_INT_CALLS.labels(op, "err").inc()
        except Exception:
            pass
        if settings.PAYMENTS_CB_ENABLED and st.fails >= max(1, int(settings.PAYMENTS_CB_THRESHOLD)):
            st.open_until = datetime.now(timezone.utc) + timedelta(seconds=max(1, int(settings.PAYMENTS_CB_COOLDOWN_SECS)))


def snapshot() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    for k, v in _STATES.items():
        out[k] = {
            "fails": v.fails,
            "open": bool(v.open_until and now < v.open_until),
            "open_until": (v.open_until.isoformat() + "Z") if v.open_until else None,
        }
    return out


def reset() -> None:
    _STATES.clear()
