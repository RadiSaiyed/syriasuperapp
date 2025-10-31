from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import Counter
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..config import settings
from ..maps import get_maps_provider

router = APIRouter(prefix="/maps", tags=["maps"])
GEOCODER_CALLS = Counter("taxi_maps_geocoder_calls_total", "Geocoder calls", ["type", "result"])  # type: reverse|search; result: ok|error
TRAFFIC_CALLS = Counter("taxi_maps_traffic_calls_total", "Traffic API calls", ["type", "result"])  # type: flow|incidents


def _ttl_cache(ttl_secs: int) -> Tuple[Callable[[str], dict | None], Callable[[str, dict], None]]:
    store: Dict[str, Tuple[datetime, dict]] = {}

    def get(key: str):
        ent = store.get(key)
        if not ent:
            return None
        exp, val = ent
        if exp >= datetime.now(timezone.utc):
            return val
        store.pop(key, None)
        return None

    def set_(key: str, val: dict):
        if ttl_secs <= 0:
            return
        store[key] = (datetime.now(timezone.utc) + timedelta(seconds=ttl_secs), val)

    return get, set_


_cache_secs = max(0, int(getattr(settings, "MAPS_GEOCODER_CACHE_SECS", 120)))
_rev_get, _rev_set = _ttl_cache(_cache_secs)
_auto_get, _auto_set = _ttl_cache(_cache_secs)


def _maps_timeout() -> float:
    return float(getattr(settings, "MAPS_TIMEOUT_SECS", 5.0))


def _maps_retries() -> int:
    return max(0, int(getattr(settings, "MAPS_MAX_RETRIES", 2)))


def _maps_backoff() -> float:
    return float(getattr(settings, "MAPS_BACKOFF_SECS", 0.25))


def _google_get(url: str, params: dict) -> dict:
    timeout = _maps_timeout()
    retries = _maps_retries()
    backoff = _maps_backoff()
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
            if resp.status_code >= 400:
                raise RuntimeError(f"maps_status_{resp.status_code}")
            data = resp.json() or {}
            if isinstance(data, dict) and "status" in data:
                st = (data.get("status") or "").upper()
                if st not in ("OK", "ZERO_RESULTS"):
                    raise RuntimeError(f"maps_status_{st}")
            return data
        except Exception as exc:  # pragma: no cover - network failures
            last_err = exc
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise last_err
    raise RuntimeError("maps_request_failed")


def _reverse_stub(lat: float, lon: float) -> dict:
    display = f"{lat:.5f},{lon:.5f}"
    return {
        "display_name": display,
        "lat": lat,
        "lon": lon,
        "address": {"freeformAddress": display},
    }


def _search_stub(query: str, limit: int) -> dict:
    items = []
    capped = max(1, min(limit, 5))
    for idx in range(capped):
        items.append(
            {
                "display_name": f"{query} {idx + 1}",
                "lat": 0.0,
                "lon": 0.0,
                "type": "stub",
                "address": {"freeformAddress": f"{query} {idx + 1}"},
            }
        )
    return {"items": items}


@router.get("/reverse")
def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    lang: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = f"rev|{lang or ''}|{lat:.6f}|{lon:.6f}"
    cached = _rev_get(key)
    if cached is not None:
        return cached

    if not settings.GOOGLE_MAPS_API_KEY:
        payload = _reverse_stub(lat, lon)
        _rev_set(key, payload)
        GEOCODER_CALLS.labels("reverse", "ok_stub").inc()
        return payload

    try:
        params = {"key": settings.GOOGLE_MAPS_API_KEY, "latlng": f"{lat:.6f},{lon:.6f}"}
        if lang:
            params["language"] = lang
        url = f"{settings.GOOGLE_MAPS_BASE_URL.rstrip('/')}/maps/api/geocode/json"
        data = _google_get(url, params)
        results = data.get("results") or []
        r0 = results[0] if results else {}
        display = r0.get("formatted_address") or f"{lat:.5f},{lon:.5f}"
        payload = {"display_name": display, "lat": lat, "lon": lon, "address": {"freeformAddress": display}}
        _rev_set(key, payload)
        GEOCODER_CALLS.labels("reverse", "ok").inc()
        return payload
    except Exception:
        GEOCODER_CALLS.labels("reverse", "error").inc()
        payload = _reverse_stub(lat, lon)
        _rev_set(key, payload)
        return payload


@router.get("/autocomplete")
def autocomplete(
    q: str = Query(..., min_length=1, strip_whitespace=True),
    limit: int = Query(5, ge=1, le=10),
    lang: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = f"auto|{lang or ''}|{q}|{limit}"
    cached = _auto_get(key)
    if cached is not None:
        return cached

    if not settings.GOOGLE_MAPS_API_KEY:
        payload = _search_stub(q, limit)
        _auto_set(key, payload)
        GEOCODER_CALLS.labels("search", "ok_stub").inc()
        return payload

    try:
        params = {"key": settings.GOOGLE_MAPS_API_KEY, "address": q}
        if lang:
            params["language"] = lang
        url = f"{settings.GOOGLE_MAPS_BASE_URL.rstrip('/')}/maps/api/geocode/json"
        data = _google_get(url, params)
        results = data.get("results") or []
        items = []
        for item in results[: max(1, min(limit, 10))]:
            geom = item.get("geometry", {})
            loc = geom.get("location", {})
            display = item.get("formatted_address") or q
            items.append({
                "display_name": display,
                "lat": loc.get("lat"),
                "lon": loc.get("lng"),
                "type": None,
                "address": {"freeformAddress": display},
            })
        payload = {"items": items}
        _auto_set(key, payload)
        GEOCODER_CALLS.labels("search", "ok").inc()
        return payload
    except Exception:
        GEOCODER_CALLS.labels("search", "error").inc()
        payload = _search_stub(q, limit)
        _auto_set(key, payload)
        return payload


@router.get("/route")
def route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    fmt: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        provider = get_maps_provider()
        dist_km, mins, poly = provider.route(
            [(from_lat, from_lon), (to_lat, to_lon)], want_polyline=True
        )
        if (fmt or "").lower() == "geojson":
            coords_out = [
                {"lat": from_lat, "lon": from_lon},
                {"lat": to_lat, "lon": to_lon},
            ]
            return {"distance_km": dist_km, "duration_mins": mins, "coords": coords_out}
        return {"distance_km": dist_km, "duration_mins": mins, "polyline6": poly}
    except Exception:
        return {"distance_km": 0.0, "duration_mins": 1, "coords": [], "polyline6": None}


@router.get("/traffic/flow_segment")
def traffic_flow_segment(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    zoom: int | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Not supported with Google Maps
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="traffic_flow_not_supported")


@router.get("/traffic/incidents")
def traffic_incidents(
    bbox: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 5.0,
    lang: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Not supported with Google Maps
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="traffic_incidents_not_supported")
