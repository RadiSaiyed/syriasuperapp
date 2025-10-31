from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from .auth import get_current_user
from .database import get_db


router = APIRouter()


connections: Dict[str, Set[WebSocket]] = {}
typing_state: Dict[str, Dict[str, bool]] = {}


def deliver_to_user(user_id: str, payload: dict):
    conns = connections.get(str(user_id)) or set()
    for ws in list(conns):
        try:
            import json
            ws.send_text(json.dumps(payload))  # type: ignore
        except Exception:
            try:
                conns.remove(ws)
            except Exception:
                pass


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    # Simple token param: ws://.../ws?token=...
    token = websocket.query_params.get("token")
    await websocket.accept()
    if not token:
        await websocket.close()
        return
    # Minimal token decode without DB dependency (avoid session in WS):
    import jwt
    from .config import settings
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = str(payload.get("sub"))
    except Exception:
        await websocket.close()
        return
    if not user_id:
        await websocket.close()
        return
    conns = connections.setdefault(user_id, set())
    conns.add(websocket)
    # Update last_seen on connect
    try:
        from .database import get_db
        from sqlalchemy.orm import Session
        from .models import User
        import contextlib
        # lightweight session
        for db in get_db():
            if isinstance(db, Session):
                u = db.get(User, user_id)
                if u:
                    import datetime as dt
                    u.last_seen = dt.datetime.now(dt.timezone.utc)
                break
    except Exception:
        pass
    try:
        while True:
            # keep the socket open; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        try:
            conns.remove(websocket)
        except Exception:
            pass
        # Update last_seen on disconnect
        try:
            from .database import get_db
            from sqlalchemy.orm import Session
            from .models import User
            for db in get_db():
                if isinstance(db, Session):
                    u = db.get(User, user_id)
                    if u:
                        import datetime as dt
                        u.last_seen = dt.datetime.now(dt.timezone.utc)
                    break
        except Exception:
            pass
