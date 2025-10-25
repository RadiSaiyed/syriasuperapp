from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re


@dataclass
class ToolDef:
    name: str
    description: str
    schema: Dict[str, Any]
    confirmation_required: bool = True


TOOLS: dict[str, ToolDef] = {
    "pay_bill": ToolDef(
        name="pay_bill",
        description="Pay a utilities bill by bill_id",
        schema={
            "type": "object",
            "properties": {
                "bill_id": {"type": "string", "description": "Target bill id"},
            },
            "required": ["bill_id"],
            "additionalProperties": False,
        },
    ),
    "start_parking_session": ToolDef(
        name="start_parking_session",
        description="Start an on-street parking session for a given zone and plate",
        schema={
            "type": "object",
            "properties": {
                "zone_id": {"type": "string"},
                "plate": {"type": "string"},
                "minutes": {"type": "integer", "minimum": 5, "maximum": 240},
            },
            "required": ["zone_id", "plate", "minutes"],
            "additionalProperties": False,
        },
    ),
    "create_car_listing": ToolDef(
        name="create_car_listing",
        description="Create a car listing with minimal fields",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "make": {"type": "string"},
                "model": {"type": "string"},
                "year": {"type": "integer"},
                "price_cents": {"type": "integer", "minimum": 0},
            },
            "required": ["title", "make", "model", "year", "price_cents"],
            "additionalProperties": False,
        },
    ),
}


def infer_tool_calls(user_text: str) -> list[dict[str, Any]]:
    text = (user_text or "").strip()
    if not text:
        return []
    calls: list[dict[str, Any]] = []
    low = text.lower()

    # pay bill: detect patterns like "pay bill 123" or "pay 123"
    m = re.search(r"pay\s+(?:bill\s+)?([a-f0-9\-]{6,})", low)
    if m and "pay_bill" in TOOLS:
        calls.append({
            "name": "pay_bill",
            "arguments": {"bill_id": m.group(1)},
            "confirmation_required": TOOLS["pay_bill"].confirmation_required,
        })

    # start parking: "park zone ZONE123 plate ABC123 for 30 min"
    mz = re.search(r"zone\s+([A-Za-z0-9\-]{3,})", low)
    mp = re.search(r"plate\s+([A-Za-z0-9\-]{3,})", low)
    mm = re.search(r"(\d{1,3})\s*(?:min|minutes)", low)
    if ("park" in low or "parking" in low) and mz and mp and mm and "start_parking_session" in TOOLS:
        calls.append({
            "name": "start_parking_session",
            "arguments": {"zone_id": mz.group(1), "plate": mp.group(1), "minutes": int(mm.group(1))},
            "confirmation_required": TOOLS["start_parking_session"].confirmation_required,
        })

    # create car listing: "sell Toyota Corolla 2010 for 3,000,000"
    if "sell" in low or "list car" in low or "insert" in low:
        mk = re.search(r"(toyota|kia|hyundai|honda|ford|nissan|bmw|mercedes|audi)", low)
        md = re.search(r"(corolla|civic|elantra|focus|accord|camry|a4|c-class)", low)
        yr = re.search(r"(19|20)\d{2}", low)
        pr = re.search(r"(\d{3,}[\.,]?\d{0,3})", low)
        if mk and md and yr and pr and "create_car_listing" in TOOLS:
            price_cents = int(re.sub(r"[^0-9]", "", pr.group(1))) * 100
            title = f"{mk.group(1).title()} {md.group(1).title()}"
            calls.append({
                "name": "create_car_listing",
                "arguments": {
                    "title": title,
                    "make": mk.group(1).title(),
                    "model": md.group(1).title(),
                    "year": int(yr.group(1) + "00") if len(yr.group(0)) == 2 else int(yr.group(0)),
                    "price_cents": price_cents,
                },
                "confirmation_required": TOOLS["create_car_listing"].confirmation_required,
            })

    return calls

