from __future__ import annotations

from typing import List
from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/v1/missions", tags=["missions"])


class Mission(BaseModel):
    id: str
    title: str
    detail: str
    progress: int = 0
    goal: int = 1
    reward: str = ""


class MissionsOut(BaseModel):
    missions: List[Mission]


@router.get("", response_model=MissionsOut)
def list_missions(user_id: str):
    # MVP static missions
    return MissionsOut(missions=[
        Mission(id="on_time_bills_3", title="3 Rechnungen pünktlich zahlen", detail="Zahle 3 Rechnungen vor Fälligkeitsdatum.", progress=0, goal=3, reward="1% Cashback"),
        Mission(id="parking_week", title="5x Parken diese Woche", detail="Starte 5 Park-Sessions in 7 Tagen.", progress=0, goal=5, reward="Freiminuten 30"),
    ])

