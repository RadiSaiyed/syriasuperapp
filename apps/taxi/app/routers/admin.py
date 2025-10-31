from fastapi import APIRouter, Depends, Header, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import hashlib
import secrets

from ..auth import get_db, get_current_user
from ..config import settings
from ..models import FraudEvent, Suspension, User, Driver
from ..payments_cb import snapshot as cb_snapshot, reset as cb_reset


router = APIRouter(prefix="/admin", tags=["admin"]) 


def require_admin(x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"), request: Request = None):
    incoming = x_admin_token or ""
    # Plain token support
    token_plain = os.getenv("ADMIN_TOKEN", getattr(settings, "ADMIN_TOKEN", ""))
    for candidate in [t.strip() for t in token_plain.split(',') if t.strip()]:
        if secrets.compare_digest(incoming, candidate):
            break
    else:
        # Hashed token support (SHA-256 hex digests)
        try:
            digest = hashlib.sha256(incoming.encode()).hexdigest().lower()
        except Exception:
            digest = ""
        ok = any(secrets.compare_digest(digest, (h or "").strip().lower()) for h in getattr(settings, "admin_token_hashes", []) or [])
        if not ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token invalid")
    allow = os.getenv("ADMIN_IP_ALLOWLIST", getattr(settings, "ADMIN_IP_ALLOWLIST", ""))
    if allow:
        ips = [ip.strip() for ip in allow.split(',') if ip.strip()]
        host = None
        try:
            if request and request.client:
                host = request.client.host
        except Exception:
            host = None
        if host and host not in ips:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_ip_blocked")


@router.get("/fraud/events")
def list_fraud_events(limit: int = 100, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    limit = max(1, min(500, limit))
    rows = db.query(FraudEvent).order_by(FraudEvent.created_at.desc()).limit(limit).all()
    out = []
    for e in rows:
        out.append({
            "id": str(e.id),
            "user_id": str(e.user_id) if e.user_id else None,
            "driver_id": str(e.driver_id) if e.driver_id else None,
            "type": e.type,
            "data": e.data or {},
            "created_at": e.created_at.isoformat() + "Z",
        })
    return {"items": out}


class SuspensionIn(BaseModel):
    user_phone: str | None = None
    driver_phone: str | None = None
    reason: str | None = None
    minutes: int | None = None  # if omitted, suspend indefinitely until manually toggled


@router.post("/suspensions")
def create_suspension(payload: SuspensionIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    if not payload.user_phone and not payload.driver_phone:
        raise HTTPException(status_code=400, detail="Provide user_phone or driver_phone")
    user_id = None
    driver_id = None
    if payload.user_phone:
        u = db.query(User).filter(User.phone == payload.user_phone).one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="user_not_found")
        user_id = u.id
    if payload.driver_phone:
        u = db.query(User).filter(User.phone == payload.driver_phone).one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="driver_user_not_found")
        d = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
        if not d:
            raise HTTPException(status_code=404, detail="driver_not_found")
        driver_id = d.id
from datetime import datetime, timedelta, timezone
    until = None
    if payload.minutes and payload.minutes > 0:
        until = datetime.now(timezone.utc) + timedelta(minutes=payload.minutes)
    s = Suspension(user_id=user_id, driver_id=driver_id, reason=(payload.reason or None), until=until, active=True)
    db.add(s); db.flush()
    return {"id": str(s.id), "active": s.active, "until": s.until.isoformat() + "Z" if s.until else None}


@router.get("/suspensions")
def list_suspensions(limit: int = 100, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    limit = max(1, min(500, limit))
    rows = db.query(Suspension).order_by(Suspension.created_at.desc()).limit(limit).all()
    out = []
    for s in rows:
        out.append({
            "id": str(s.id),
            "user_id": str(s.user_id) if s.user_id else None,
            "driver_id": str(s.driver_id) if s.driver_id else None,
            "reason": s.reason,
            "until": s.until.isoformat() + "Z" if s.until else None,
            "active": s.active,
            "created_at": s.created_at.isoformat() + "Z",
        })
    return {"items": out}


@router.get("/suspensions/active")
def list_active_suspensions(phone: str | None = None, driver_phone: str | None = None, limit: int = 100, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    q = db.query(Suspension).filter(Suspension.active == True)  # noqa: E712
    if phone:
        u = db.query(User).filter(User.phone == phone).one_or_none()
        if u:
            q = q.filter(Suspension.user_id == u.id)
        else:
            return {"items": []}
    if driver_phone:
        u = db.query(User).filter(User.phone == driver_phone).one_or_none()
        if u:
            d = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
            if d:
                q = q.filter(Suspension.driver_id == d.id)
            else:
                return {"items": []}
        else:
            return {"items": []}
    rows = q.order_by(Suspension.created_at.desc()).limit(max(1, min(500, limit))).all()
    out = []
    for s in rows:
        out.append({
            "id": str(s.id),
            "user_id": str(s.user_id) if s.user_id else None,
            "driver_id": str(s.driver_id) if s.driver_id else None,
            "reason": s.reason,
            "until": s.until.isoformat() + "Z" if s.until else None,
            "active": s.active,
            "created_at": s.created_at.isoformat() + "Z",
        })
    return {"items": out}


class ToggleIn(BaseModel):
    active: bool


@router.post("/suspensions/{susp_id}/toggle")
def toggle_suspension(susp_id: str, payload: ToggleIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    s = db.get(Suspension, susp_id)
    if not s:
        raise HTTPException(status_code=404, detail="not_found")
    s.active = bool(payload.active)
    db.flush()
    return {"id": susp_id, "active": s.active}


class UnsuspendIn(BaseModel):
    user_phone: str | None = None
    driver_phone: str | None = None


@router.post("/suspensions/unsuspend")
def unsuspend_target(payload: UnsuspendIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    if not payload.user_phone and not payload.driver_phone:
        raise HTTPException(status_code=400, detail="Provide user_phone or driver_phone")
    updated = 0
    if payload.user_phone:
        u = db.query(User).filter(User.phone == payload.user_phone).one_or_none()
        if u:
            rows = db.query(Suspension).filter(Suspension.user_id == u.id, Suspension.active == True).all()  # noqa: E712
            for s in rows:
                s.active = False
                updated += 1
    if payload.driver_phone:
        u = db.query(User).filter(User.phone == payload.driver_phone).one_or_none()
        if u:
            d = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
            if d:
                rows = db.query(Suspension).filter(Suspension.driver_id == d.id, Suspension.active == True).all()  # noqa: E712
                for s in rows:
                    s.active = False
                    updated += 1
    db.flush()
    return {"unsuspended": updated}


@router.get("/user")
def get_user(phone: str, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="user_not_found")
    drv = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
    susp = db.query(Suspension).filter(((Suspension.user_id == u.id) | (Suspension.driver_id == (drv.id if drv else None)))).order_by(Suspension.created_at.desc()).all()
    return {
        "id": str(u.id),
        "phone": u.phone,
        "name": u.name,
        "role": u.role,
        "driver": ({
            "id": str(drv.id),
            "status": drv.status,
            "vehicle_make": drv.vehicle_make,
            "vehicle_plate": drv.vehicle_plate,
            "ride_class": getattr(drv, 'ride_class', None),
        } if drv else None),
        "suspensions": [
            {
                "id": str(s.id),
                "active": s.active,
                "reason": s.reason,
                "until": s.until.isoformat() + "Z" if s.until else None,
                "created_at": s.created_at.isoformat() + "Z",
            }
            for s in susp
        ],
    }


@router.get("/ui", include_in_schema=False)
def admin_ui(request: Request, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    # Minimal HTML UI to list recent fraud events and active suspensions
    events = db.query(FraudEvent).order_by(FraudEvent.created_at.desc()).limit(50).all()
    susp = db.query(Suspension).filter(Suspension.active == True).order_by(Suspension.created_at.desc()).limit(50).all()  # noqa: E712
    def esc(s: str) -> str:
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') if s else ''
    html = ["<html><head><title>Taxi Admin</title></head><body>"]
    html.append("<h2>Active Suspensions</h2><ul>")
    for s in susp:
        html.append(f"<li>{esc(str(s.id))} active={s.active} until={esc(s.until.isoformat()+'Z' if s.until else '-')}</li>")
    html.append("</ul>")


class DriverClassIn(BaseModel):
    driver_phone: str
    ride_class: str


@router.post("/driver/set_class")
def admin_set_driver_class(payload: DriverClassIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    phone = payload.driver_phone.strip()
    cls = payload.ride_class.strip().lower()
    if not phone or not cls:
        raise HTTPException(status_code=400, detail="invalid_input")
    if cls not in (settings.RIDE_CLASS_MULTIPLIERS.keys()):
        raise HTTPException(status_code=400, detail="unknown_class")
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="driver_user_not_found")
    d = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="driver_not_found")
    d.ride_class = cls
    db.flush()
    return {"driver_id": str(d.id), "ride_class": d.ride_class}


@router.get("/report/ride_classes")
def admin_report_ride_classes(db: Session = Depends(get_db), _: None = Depends(require_admin)):
    from sqlalchemy import func
    from ..models import Ride
    rows = (
        db.query(
            getattr(Ride, 'ride_class'),
            func.count(Ride.id),
            func.coalesce(func.sum(Ride.quoted_fare_cents), 0),
            func.coalesce(func.sum(Ride.final_fare_cents), 0),
        )
        .group_by(getattr(Ride, 'ride_class'))
        .all()
    )
    items = []
    for cls, cnt, sum_quoted, sum_final in rows:
        items.append({
            "ride_class": cls or None,
            "count": int(cnt or 0),
            "sum_quoted_cents": int(sum_quoted or 0),
            "sum_final_cents": int(sum_final or 0),
        })
    return {"items": items}


class DriverPromoteIn(BaseModel):
    phone: str
    name: str | None = None
    ride_class: str | None = None
    vehicle_make: str | None = None
    vehicle_plate: str | None = None


@router.post("/driver/promote")
def admin_promote_driver(payload: DriverPromoteIn, db: Session = Depends(get_db), _: None = Depends(require_admin)):
    phone = payload.phone.strip()
    if not phone or not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="invalid_phone")
    # Ensure user exists with role 'driver'
    u = db.query(User).filter(User.phone == phone).one_or_none()
    if not u:
        u = User(phone=phone, name=(payload.name or None), role="driver")
        db.add(u); db.flush()
    else:
        if u.role != "driver":
            u.role = "driver"
    # Ensure driver row
    d = db.query(Driver).filter(Driver.user_id == u.id).one_or_none()
    if not d:
        d = Driver(user_id=u.id, status="offline")
        db.add(d); db.flush()
    # Set vehicle
    if payload.vehicle_make is not None:
        d.vehicle_make = payload.vehicle_make.strip() or None
    if payload.vehicle_plate is not None:
        d.vehicle_plate = payload.vehicle_plate.strip() or None
    # Set class (validate against configured classes)
    cls = (payload.ride_class or "").strip().lower()
    if cls:
        if cls not in settings.RIDE_CLASS_MULTIPLIERS.keys():
            raise HTTPException(status_code=400, detail="unknown_class")
        d.ride_class = cls
    db.flush()
    # Ensure taxi wallet exists
    try:
        from ..models import TaxiWallet
        w = db.query(TaxiWallet).filter(TaxiWallet.driver_id == d.id).one_or_none()
        if not w:
            db.add(TaxiWallet(driver_id=d.id, balance_cents=0)); db.flush()
    except Exception:
        pass
    return {
        "user_id": str(u.id),
        "driver_id": str(d.id),
        "phone": u.phone,
        "name": u.name,
        "ride_class": getattr(d, 'ride_class', None),
        "vehicle_make": d.vehicle_make,
        "vehicle_plate": d.vehicle_plate,
        "status": d.status,
    }


@router.get("/drivers")
def admin_list_drivers(
    ride_class: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """List drivers with optional class filter and search (phone/name)."""
    from sqlalchemy import or_
    limit = max(1, min(1000, int(limit)))
    offset = max(0, int(offset))
    query = db.query(Driver, User).join(User, Driver.user_id == User.id)
    if ride_class:
        cls = ride_class.strip().lower()
        query = query.filter(Driver.ride_class == cls)
    if q and q.strip():
        s = f"%{q.strip()}%"
        query = query.filter(or_(User.phone.ilike(s), User.name.ilike(s)))
    rows = query.order_by(Driver.created_at.desc()).offset(offset).limit(limit).all()
    out = []
    for d, u in rows:
        out.append({
            "driver_id": str(d.id),
            "phone": u.phone,
            "name": u.name,
            "status": d.status,
            "ride_class": getattr(d, 'ride_class', None),
            "created_at": d.created_at.isoformat() + "Z",
        })
    return {"items": out, "limit": limit, "offset": offset}
    html.append("<h2>Recent Fraud Events</h2><ul>")
    for e in events:
        html.append(f"<li>{esc(e.type)} at {esc(e.created_at.isoformat()+'Z')}</li>")
    html.append("</ul>")
    # Payments CB status + reset button
    tok = request.headers.get('X-Admin-Token', '')
    html.append("<h2>Payments Circuit Breaker</h2>")
    html.append("<button id=cbreset>CB Reset</button> <span id=cbmsg></span>")
    html.append("<script>document.getElementById('cbreset').onclick = async function(){\n  const r = await fetch('/admin/payments/cb_reset', {method:'POST', headers:{'X-Admin-Token':'" + esc(tok) + "'}});\n  document.getElementById('cbmsg').innerText = r.ok ? 'reset ok' : ('error ' + r.status);\n  setTimeout(()=>{location.reload();}, 500);\n};</script>")
    html.append("<ul>")
    for op, st in cb_snapshot().items():
        html.append(f"<li>{esc(op)}: fails={int(st.get('fails',0))}, open={st.get('open')}, until={esc(st.get('open_until') or '-')}</li>")
    html.append("</ul>")
    html.append("</body></html>")
    return Response("\n".join(html), media_type="text/html")


@router.get("/payments/cb_status")
def payments_cb_status(_: None = Depends(require_admin)):
    return {"states": cb_snapshot()}


@router.post("/payments/cb_reset")
def payments_cb_reset(_: None = Depends(require_admin)):
    cb_reset()
    return {"detail": "ok"}
