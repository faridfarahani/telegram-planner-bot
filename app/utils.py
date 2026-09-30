from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import jdatetime

from .constants import DAY_LABELS, PY_WEEKDAY_TO_CODE

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_digits(value: object) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def local_now(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def local_date_iso(timezone_name: str) -> str:
    return local_now(timezone_name).date().isoformat()


def day_code_for_date(value: date) -> str:
    return PY_WEEKDAY_TO_CODE[value.weekday()]


def jalali_date_label(gregorian_iso: str) -> str:
    value = date.fromisoformat(gregorian_iso)
    jalali = jdatetime.date.fromgregorian(date=value)
    return fa_digits(f"{jalali.year:04d}/{jalali.month:02d}/{jalali.day:02d}")


def weekday_label(gregorian_iso: str) -> str:
    value = date.fromisoformat(gregorian_iso)
    return DAY_LABELS[day_code_for_date(value)]


def format_history_line(local_date: str, local_time: str, ordinal: int, required_ticks: int) -> str:
    return (
        f"• {weekday_label(local_date)} {jalali_date_label(local_date)} - "
        f"{fa_digits(local_time[:5])} | تیک {fa_digits(ordinal)} از {fa_digits(required_ticks)}"
    )
