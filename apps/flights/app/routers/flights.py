from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models import Airline, Flight, User, FlightSeat
from ..schemas import SearchFlightsIn, SearchFlightsOut, FlightOut, FlightSeatsOut


router = APIRouter(prefix="/flights", tags=["flights"])


def _seed_dev_data(db: Session):
    if db.query(Airline).count() > 0:
        return
    ops = [
        Airline(name="Sham Wings"),
        Airline(name="Syrian Air"),
    ]
    db.add_all(ops)
    db.flush()
    now = datetime.utcnow()
    flights = []
    for op in ops:
        for d in range(0, 2):
            day = now + timedelta(days=d)
            base = day.replace(hour=7, minute=0, second=0, microsecond=0)
            flights.extend([
                Flight(airline_id=op.id, origin="Damascus (DAM)", destination="Aleppo (ALP)", depart_at=base, arrive_at=base + timedelta(hours=1), price_cents=150000, seats_total=180, seats_available=180),
                Flight(airline_id=op.id, origin="Damascus (DAM)", destination="Latakia (LTK)", depart_at=base + timedelta(hours=3), arrive_at=base + timedelta(hours=4), price_cents=120000, seats_total=180, seats_available=180),
            ])
    db.add_all(flights)
    db.flush()


@router.post("/search", response_model=SearchFlightsOut)
def search_flights(payload: SearchFlightsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user:  # noqa: F841
        pass
    _seed_dev_data(db)

    start = datetime.combine(payload.date, datetime.min.time())
    end = start + timedelta(days=1)
    q = (
        db.query(Flight, Airline)
        .join(Airline, Airline.id == Flight.airline_id)
        .filter(Flight.origin.ilike(f"%{payload.origin}%"))
        .filter(Flight.destination.ilike(f"%{payload.destination}%"))
        .filter(Flight.depart_at >= start)
        .filter(Flight.depart_at < end)
        .order_by(Flight.depart_at.asc())
    )
    rows = q.all()
    return SearchFlightsOut(
        flights=[
            FlightOut(
                id=str(f.id),
                airline_name=al.name,
                origin=f.origin,
                destination=f.destination,
                depart_at=f.depart_at,
                arrive_at=f.arrive_at,
                price_cents=f.price_cents,
                seats_available=f.seats_available,
            )
            for (f, al) in rows
        ]
    )


@router.get("/{flight_id}", response_model=FlightOut)
def get_flight(flight_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(Flight, flight_id)
    if f is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Flight not found")
    al = db.get(Airline, f.airline_id)
    return FlightOut(
        id=str(f.id),
        airline_name=al.name if al else "",
        origin=f.origin,
        destination=f.destination,
        depart_at=f.depart_at,
        arrive_at=f.arrive_at,
        price_cents=f.price_cents,
        seats_available=f.seats_available,
    )


@router.get("/{flight_id}/seats", response_model=FlightSeatsOut)
def flight_seats(flight_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = db.get(Flight, flight_id)
    if f is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Flight not found")
    rows = db.query(FlightSeat).filter(FlightSeat.flight_id == f.id).all()
    reserved = sorted([int(r.seat_number) for r in rows if r.booking_id is not None])
    return FlightSeatsOut(flight_id=str(f.id), seats_total=f.seats_total, reserved=reserved)
