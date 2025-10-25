from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from math import radians, cos, sin, asin, sqrt
from ..auth import get_current_user, get_db
from ..models import Facility


router = APIRouter(prefix="/facilities", tags=["facilities"])


def _hk(lat1, lon1, lat2, lon2):
    R = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(d_lon/2)**2
    return 2*asin(sqrt(a))*R


class FacilityOut(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    height_limit_m: float | None = None
    distance_m: int


@router.get("/near", response_model=list[FacilityOut])
def near(lat: float, lon: float, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Facility).all()
    out = []
    for f in rows:
        dist = int(_hk(lat, lon, f.lat, f.lon) * 1000)
        out.append(FacilityOut(id=str(f.id), name=f.name, lat=f.lat, lon=f.lon, height_limit_m=f.height_limit_m, distance_m=dist))
    out.sort(key=lambda x: x.distance_m)
    return out[:20]

