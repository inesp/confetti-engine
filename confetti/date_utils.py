import calendar
from datetime import date

MONTH_ABBR = {i: calendar.month_abbr[i] for i in range(1, 13)}


def parse_month_day(mm_dd: str) -> tuple[int, int]:
    """Parse 'MM-DD' string into (month, day)."""
    parts = mm_dd.split("-")
    return int(parts[0]), int(parts[1])


def format_date(some_date: date) -> str | None:
    """Convert to '1. Oct 2026' style."""
    formatted = f"{some_date.day}. {MONTH_ABBR[some_date.month]} {some_date.year}"
    return formatted
