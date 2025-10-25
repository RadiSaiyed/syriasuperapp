from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import Operator, Trip, User, TripSeat
from ..schemas import SearchTripsIn, SearchTripsOut, TripOut, TripSeatsOut


router = APIRouter(prefix="/trips", tags=["trips"])


def _seed_dev_data(db: Session):
    if db.query(Operator).count() > 0:
        return
    ops = [
        Operator(name="JABER Bus"),
        Operator(name="Sham Lines"),
    ]
    db.add_all(ops)
    db.flush()
    now = datetime.utcnow()
    trips = []
    for op in ops:
        # Seed Damascus -> Aleppo and Damascus -> Homs for next 2 days
        for d in range(0, 2):
            day = now + timedelta(days=d)
            base = day.replace(hour=6, minute=0, second=0, microsecond=0)
            trips.extend([
                Trip(operator_id=op.id, origin="Damascus", destination="Aleppo", depart_at=base, arrive_at=base + timedelta(hours=5), price_cents=20000, seats_total=40, seats_available=40, bus_model="Volvo B11R", bus_year=2019),
                Trip(operator_id=op.id, origin="Damascus", destination="Aleppo", depart_at=base + timedelta(hours=4), arrive_at=base + timedelta(hours=9), price_cents=22000, seats_total=40, seats_available=40, bus_model="Mercedes Tourismo", bus_year=2018),
                Trip(operator_id=op.id, origin="Damascus", destination="Homs", depart_at=base + timedelta(hours=1), arrive_at=base + timedelta(hours=3), price_cents=12000, seats_total=40, seats_available=40, bus_model="Isuzu Turquoise", bus_year=2020),
            ])
    db.add_all(trips)
    db.flush()


@router.post("/search", response_model=SearchTripsOut)
def search_trips(payload: SearchTripsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user:  # noqa: F841
        pass
    # Seed dev data on first use
    _seed_dev_data(db)

    start = datetime.combine(payload.date, datetime.min.time())
    end = start + timedelta(days=1)
    q = (
        db.query(Trip, Operator)
        .join(Operator, Operator.id == Trip.operator_id)
        .filter(Trip.origin.ilike(payload.origin))
        .filter(Trip.destination.ilike(payload.destination))
        .filter(Trip.depart_at >= start)
        .filter(Trip.depart_at < end)
        .order_by(Trip.depart_at.asc())
    )
    rows = q.all()
    return SearchTripsOut(
        trips=[
            TripOut(
                id=str(t.id),
                operator_name=op.name,
                origin=t.origin,
                destination=t.destination,
                depart_at=t.depart_at,
                arrive_at=t.arrive_at,
                price_cents=t.price_cents,
                seats_available=t.seats_available,
                bus_model=t.bus_model,
                bus_year=t.bus_year,
            )
            for (t, op) in rows
        ]
    )


@router.get("/{trip_id}", response_model=TripOut)
def get_trip(trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Trip, trip_id)
    if t is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trip not found")
    op = db.get(Operator, t.operator_id)
    return TripOut(
        id=str(t.id),
        operator_name=op.name if op else "",
        origin=t.origin,
        destination=t.destination,
        depart_at=t.depart_at,
        arrive_at=t.arrive_at,
        price_cents=t.price_cents,
        seats_available=t.seats_available,
        bus_model=t.bus_model,
        bus_year=t.bus_year,
    )


@router.get("/{trip_id}/seats", response_model=TripSeatsOut)
def trip_seats(trip_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Trip, trip_id)
    if t is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trip not found")
    rows = db.query(TripSeat).filter(TripSeat.trip_id == t.id).all()
    reserved = sorted([int(r.seat_number) for r in rows if r.booking_id is not None])
    return TripSeatsOut(trip_id=str(t.id), seats_total=t.seats_total, reserved=reserved)
