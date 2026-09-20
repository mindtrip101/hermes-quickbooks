from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _quarter(day: date) -> tuple[date, date]:
    q = (day.month - 1) // 3
    start = date(day.year, q * 3 + 1, 1)
    if q == 3:
        end = date(day.year, 12, 31)
    else:
        end = date(day.year, (q + 1) * 3 + 1, 1) - timedelta(days=1)
    return start, end


def _last_quarter(day: date) -> tuple[date, date]:
    q = (day.month - 1) // 3
    if q == 0:
        return date(day.year - 1, 10, 1), date(day.year - 1, 12, 31)
    start = date(day.year, (q - 1) * 3 + 1, 1)
    end = date(day.year, q * 3 + 1, 1) - timedelta(days=1)
    return start, end


def resolve_period(args: dict[str, Any], today: date | None = None) -> tuple[date, date, str]:
    today = today or date.today()
    period = str(args.get("period") or "").strip().lower()
    start_raw = str(args.get("start_date") or "").strip()
    end_raw = str(args.get("end_date") or "").strip()
    if start_raw and end_raw:
        return date.fromisoformat(start_raw), date.fromisoformat(end_raw), "explicit"
    if period in {"this_month", "current_month"}:
        start = today.replace(day=1)
        return start, today, period
    if period in {"last_month"}:
        first = today.replace(day=1)
        end = first - timedelta(days=1)
        return end.replace(day=1), end, period
    if period in {"this_quarter", "qtd", "q3"} and period != "q3":
        start, end = _quarter(today)
        return start, min(end, today), period
    if period == "q3":
        start, end = date(today.year, 7, 1), date(today.year, 9, 30)
        return start, min(end, today) if today.month >= 7 else end, period
    if period in {"last_quarter"}:
        return (*_last_quarter(today), period)
    if period in {"this_year", "ytd"}:
        return date(today.year, 1, 1), today, period
    if period in {"last_year"}:
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), period
    start = today.replace(day=1)
    return start, today, "this_month"


def iso(day: date) -> str:
    return day.isoformat()
