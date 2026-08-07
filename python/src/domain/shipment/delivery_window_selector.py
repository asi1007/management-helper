from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any

DEFAULT_LEAD_MONTHS = 1


def add_months(base: date, months: int) -> date:
    total_month_index = base.month - 1 + months
    year = base.year + total_month_index // 12
    month = total_month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def select_delivery_window_option_id(
    options: list[dict[str, Any]],
    *,
    ship_date: date,
    lead_days: int | None = None,
) -> str:
    target_date = _resolve_target_date(ship_date, lead_days)
    available = [o for o in options if o.get("availabilityType") == "AVAILABLE"]
    if not available:
        raise RuntimeError("選択可能な配送ウィンドウがありません")
    nearest = min(available, key=lambda o: abs((_start_date_of(o) - target_date).days))
    return str(nearest["deliveryWindowOptionId"])


def _resolve_target_date(ship_date: date, lead_days: int | None) -> date:
    if lead_days is None:
        return add_months(ship_date, DEFAULT_LEAD_MONTHS)
    return date.fromordinal(ship_date.toordinal() + lead_days)


def _start_date_of(option: dict[str, Any]) -> date:
    raw = str(option.get("startDate") or "")
    return datetime.strptime(raw[:10], "%Y-%m-%d").date()
