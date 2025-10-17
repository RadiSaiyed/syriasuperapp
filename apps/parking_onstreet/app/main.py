from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, SessionLocal
from .models import Base, Zone, Tariff
from .routers import zones as zones_router
from .routers import sessions as sessions_router
from .routers import receipts as receipts_router
from .routers import reminders as reminders_router
from .routers import internal_tools as internal_tools_router

app = FastAPI(title="Parking On‑Street")
allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
    # Seed demo zone/tariff if empty
    db: Session = SessionLocal()
    try:
        if db.query(Zone).count() == 0:
            z = Zone(
                name="Damascus – Zone A",
                center_lat=33.5138,
                center_lon=36.2765,
                radius_m=600,
            )
            db.add(z)
            db.flush()
            t = Tariff(
                zone_id=z.id,
                currency="SYP",
                per_minute_cents=50,
                min_minutes=10,
                free_minutes=0,
                max_daily_cents=30000,
                service_fee_bps=200,
            )
            db.add(t)
            db.commit()
    finally:
        db.close()


app.include_router(zones_router.router)
app.include_router(sessions_router.router)
app.include_router(receipts_router.router)
app.include_router(reminders_router.router)
app.include_router(internal_tools_router.router)

@app.get("/health")
def health():
    return {"status": "ok"}
