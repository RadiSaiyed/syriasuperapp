from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List
import httpx
import time

from .config import settings
from .utils import haversine_km


def _decode_polyline5(poly: str) -> list[tuple[float, float]]:
    # Basic Google encoded polyline decoder (precision 1e-5)
    points: list[tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(poly)
    while index < length:
        result = 0
        shift = 0
        b = 0
        while True:
            b = ord(poly[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = 0
        shift = 0
        while True:
            b = ord(poly[index]) - 63
            index += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append((lat / 1e5, lng / 1e5))
    return points


class GoogleMapsProvider:
    """Google Maps routing provider with optional offline fallback for dev/test."""

    def __init__(self) -> None:
        self.base_url = settings.GOOGLE_MAPS_BASE_URL.rstrip("/")
        self.api_key = (settings.GOOGLE_MAPS_API_KEY or "").strip()
        self.use_traffic = bool(getattr(settings, "GOOGLE_USE_TRAFFIC", True))
        self.cache_ttl = max(0, int(getattr(settings, "MAPS_ROUTE_CACHE_SECS", 60)))
        self._cache: dict[str, tuple[datetime, tuple[float, int, str | None]]] = {}

    def _cache_get(self, key: str):
        if self.cache_ttl <= 0:
            return None
        ent = self._cache.get(key)
        if not ent:
            return None
        exp, val = ent
        if exp >= datetime.now(timezone.utc):
            return val
        self._cache.pop(key, None)
        return None

    def _cache_set(self, key: str, value: tuple[float, int, str | None]):
        if self.cache_ttl <= 0:
            return
        self._cache[key] = (datetime.now(timezone.utc) + timedelta(seconds=self.cache_ttl), value)

    def _offline_route(self, points: List[tuple[float, float]]) -> tuple[float, int, str | None]:
        dist = 0.0
        speed = max(1e-3, float(getattr(settings, "AVG_SPEED_KMPH", 30.0)))
        for i in range(len(points) - 1):
            (lat1, lon1), (lat2, lon2) = points[i], points[i + 1]
            dist += haversine_km(lat1, lon1, lat2, lon2)
        mins = int(round((dist / speed) * 60.0))
        return dist, max(1, mins), None

    def route(self, points: List[tuple[float, float]], want_polyline: bool = False) -> tuple[float, int, str | None]:
        if len(points) < 2:
            return 0.0, 1, None
        cache_key = f"google|{'poly' if want_polyline else 'nop'}|{points}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        # Offline fallback if no API key configured
        if not self.api_key:
            result = self._offline_route(points)
            self._cache_set(cache_key, result)
            return result
        try:
            # Use Google Directions API
            url = f"{self.base_url}/maps/api/directions/json"
            origin = f"{points[0][0]:.6f},{points[0][1]:.6f}"
            destination = f"{points[-1][0]:.6f},{points[-1][1]:.6f}"
            waypoints = None
            if len(points) > 2:
                # Preserve stops order
                wp = [f"{lat:.6f},{lon:.6f}" for (lat, lon) in points[1:-1]]
                waypoints = "|".join(wp)
            params = {
                "key": self.api_key,
                "origin": origin,
                "destination": destination,
                "mode": "driving",
            }
            if waypoints:
                params["waypoints"] = waypoints
            if self.use_traffic:
                params["departure_time"] = "now"
                params["traffic_model"] = "best_guess"
            timeout = float(getattr(settings, "MAPS_TIMEOUT_SECS", 5.0))
            retries = max(0, int(getattr(settings, "MAPS_MAX_RETRIES", 2)))
            backoff = float(getattr(settings, "MAPS_BACKOFF_SECS", 0.25))
            last_err: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    with httpx.Client(timeout=timeout) as client:
                        resp = client.get(url, params=params)
                    if resp.status_code >= 400:
                        raise RuntimeError(f"google_bad_status_{resp.status_code}")
                    body = resp.json() or {}
                    if (body.get("status") or "").upper() not in ("OK", "ZERO_RESULTS"):
                        raise RuntimeError(f"google_status_{body.get('status')}")
                    routes = body.get("routes") or []
                    if not routes:
                        raise RuntimeError("google_no_routes")
                    r0 = routes[0] or {}
                    legs = r0.get("legs") or []
                    dist_m = 0
                    dur_s = 0
                    for leg in legs:
                        d = (leg.get("distance") or {}).get("value") or 0
                        dist_m += int(d)
                        # Prefer duration_in_traffic when available
                        dur = (leg.get("duration_in_traffic") or {}).get("value")
                        if dur is None:
                            dur = (leg.get("duration") or {}).get("value") or 0
                        dur_s += int(dur)
                    dist_km = float(dist_m) / 1000.0
                    mins = int(round(float(max(60, dur_s)) / 60.0))
                    polyline = None
                    if want_polyline:
                        enc = (r0.get("overview_polyline") or {}).get("points")
                        if enc:
                            pts = _decode_polyline5(enc)
                            if pts:
                                polyline = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in pts])
                    result = (dist_km, max(1, mins), polyline)
                    self._cache_set(cache_key, result)
                    return result
                except Exception as exc:  # pragma: no cover - network failures
                    last_err = exc
                    if attempt < retries:
                        time.sleep(backoff * (2 ** attempt))
                        continue
            raise last_err or RuntimeError("google_route_failed")
        except Exception:
            result = self._offline_route(points)
            self._cache_set(cache_key, result)
            return result

    def eta_minutes(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> int:
        _, mins, _ = self.route([(from_lat, from_lon), (to_lat, to_lon)], want_polyline=False)
        return max(1, mins)

    def route_distance_duration(self, points: List[tuple[float, float]]) -> tuple[float, int]:
        dist_km, mins, _ = self.route(points, want_polyline=False)
        return dist_km, mins


_provider: GoogleMapsProvider | None = None


def get_maps_provider() -> GoogleMapsProvider:
    global _provider
    if _provider is None:
        _provider = GoogleMapsProvider()
    return _provider
