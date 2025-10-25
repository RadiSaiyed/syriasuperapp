from datetime import datetime
from math import ceil


def compute_fee(start: datetime, stop: datetime, tariff) -> tuple[int, int, int, int]:
    minutes = max(0, int(ceil((stop - start).total_seconds() / 60)))
    minutes_eff = max(0, minutes - (tariff.free_minutes or 0))
    if tariff.min_minutes:
        minutes_eff = max(minutes_eff, tariff.min_minutes)
    gross = minutes_eff * (tariff.per_minute_cents or 0)
    if tariff.max_daily_cents:
        days = max(1, ceil(minutes / (60 * 24)))
        gross = min(gross, days * tariff.max_daily_cents)
    fee = int(round(gross * (tariff.service_fee_bps or 0) / 10000.0))
    net = gross - fee
    return minutes, gross, fee, net

