from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import engine, SessionLocal
from .models import Base, Facility
from .routers import facilities as facilities_router
from .routers import reservations as reservations_router
from .routers import entries as entries_router
from .routers import operator as operator_router
from .routers import payments_webhook as payments_webhook_router

app = FastAPI(title="Parking Off‑Street")
allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    if settings.AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS payment_request_id VARCHAR(64)")
                conn.exec_driver_sql("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS payment_transfer_id VARCHAR(64)")
                conn.exec_driver_sql("ALTER TABLE entries ADD COLUMN IF NOT EXISTS payment_request_id VARCHAR(64)")
                conn.exec_driver_sql("ALTER TABLE entries ADD COLUMN IF NOT EXISTS payment_transfer_id VARCHAR(64)")
        except Exception:
            pass
    db: Session = SessionLocal()
    try:
        if db.query(Facility).count() == 0:
            f = Facility(name="City Garage A", lat=33.5100, lon=36.2750, height_limit_m=2.1)
            db.add(f)
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(facilities_router.router)
app.include_router(reservations_router.router)
app.include_router(entries_router.router)
app.include_router(payments_webhook_router.router)
app.include_router(operator_router.router)
