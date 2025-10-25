import asyncio
from typing import Dict, Set
from fastapi import WebSocket


class RideWSManager:
    def __init__(self) -> None:
        self._conns: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ride_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._conns.setdefault(ride_id, set()).add(ws)

    async def disconnect(self, ride_id: str, ws: WebSocket):
        async with self._lock:
            conns = self._conns.get(ride_id)
            if conns and ws in conns:
                conns.remove(ws)
            if conns and not conns:
                self._conns.pop(ride_id, None)

    async def broadcast_ride_status(self, ride_id: str, payload: dict):
        async with self._lock:
            conns = list(self._conns.get(ride_id, set()))
        to_remove = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                to_remove.append(ws)
        if to_remove:
            async with self._lock:
                conns_set = self._conns.get(ride_id)
                if conns_set:
                    for ws in to_remove:
                        conns_set.discard(ws)
                if conns_set and not conns_set:
                    self._conns.pop(ride_id, None)


ride_ws_manager = RideWSManager()


class DriverWSManager:
    def __init__(self) -> None:
        self._conns: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, driver_id: str, ws: WebSocket):
        await ws.accept()
        key = f"driver:{driver_id}"
        async with self._lock:
            self._conns.setdefault(key, set()).add(ws)

    async def disconnect(self, driver_id: str, ws: WebSocket):
        key = f"driver:{driver_id}"
        async with self._lock:
            conns = self._conns.get(key)
            if conns and ws in conns:
                conns.remove(ws)
            if conns and not conns:
                self._conns.pop(key, None)

    async def broadcast_to_driver(self, driver_id: str, payload: dict):
        key = f"driver:{driver_id}"
        async with self._lock:
            conns = list(self._conns.get(key, set()))
        to_remove = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                to_remove.append(ws)
        if to_remove:
            async with self._lock:
                conns_set = self._conns.get(key)
                if conns_set:
                    for ws in to_remove:
                        conns_set.discard(ws)
                if conns_set and not conns_set:
                    self._conns.pop(key, None)


driver_ws_manager = DriverWSManager()
