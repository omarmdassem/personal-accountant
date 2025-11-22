# app/period_ym.py
"""
Helpers for working with accounting periods.

Definitions
- ym: integer YYYYMM, e.g., 202501 for Jan 2025
- "MM/YY": human input like "01/25"

Public API (back-compat):
- ym_from_date(date) -> int
- mm_yy_to_ym("MM/YY") -> int
- ym_to_mm_yy(YYYYMM) -> "MM/YY"
- is_mm_yy("MM/YY") -> bool
- parse_mm_yy("MM/YY") -> int          # alias of mm_yy_to_ym (back-compat)
- format_ym(YYYYMM) -> "MM/YY"         # alias of ym_to_mm_yy (back-compat)
- validate_line_frequency_fields(...)  # monthly / one_time field combo checks
"""

from __future__ import annotations

from datetime import date
from typing import Optional

__all__ = [
    "ym_from_date",
    "mm_yy_to_ym",
    "ym_to_mm_yy",
    "is_mm_yy",
    "parse_mm_yy",
    "format_ym",
    "validate_line_frequency_fields",
]


# ---------- Conversions ----------


def ym_from_date(d: date) -> int:
    """Convert a Python date to YYYYMM integer. Example: 2025-01-15 -> 202501."""
    return d.year * 100 + d.month


def _yyyy_from_two_digit(two_digit: int) -> int:
    """
    Map two-digit year to 4-digit year.
    Policy: 00-99 -> 2000-2099 (sufficient for personal finance horizon).
    """
    if two_digit < 0 or two_digit > 99:
        raise ValueError("YY must be 00–99")
    return 2000 + two_digit


def mm_yy_to_ym(mm_yy: str) -> int:
    """
    Convert 'MM/YY' string to YYYYMM integer.
    Examples: '01/25' -> 202501, '12/30' -> 203012.
    """
    if not mm_yy or not isinstance(mm_yy, str):
        raise ValueError("MM/YY string is required")
    s = mm_yy.strip()
    parts = s.split("/")
    if len(parts) != 2:
        raise ValueError("Invalid MM/YY format; expected 'MM/YY'")
    mm, yy = parts[0].strip(), parts[1].strip()
    if len(mm) != 2 or len(yy) != 2 or not mm.isdigit() or not yy.isdigit():
        raise ValueError(
            "Invalid MM/YY; use two digits for month and year, e.g. '01/25'"
        )
    m = int(mm)
    if m < 1 or m > 12:
        raise ValueError("Month must be 01–12")
    y = _yyyy_from_two_digit(int(yy))
    return y * 100 + m


def ym_to_mm_yy(ym: int) -> str:
    """Convert YYYYMM integer to 'MM/YY' string."""
    if not isinstance(ym, int) or ym < 10000:
        raise ValueError("ym must be an integer like 202501")
    y = ym // 100
    m = ym % 100
    if m < 1 or m > 12:
        raise ValueError("Invalid ym month component")
    return f"{m:02d}/{y % 100:02d}"


def is_mm_yy(s: str) -> bool:
    """Return True if string parses as 'MM/YY'."""
    try:
        mm_yy_to_ym(s)
        return True
    except Exception:
        return False


# Back-compat names used elsewhere in the app/templates


def parse_mm_yy(mm_yy: str) -> int:
    """Alias to keep older call sites working."""
    return mm_yy_to_ym(mm_yy)


def format_ym(ym: int) -> str:
    """Alias to keep older call sites working."""
    return ym_to_mm_yy(ym)


# ---------- Validation for frequency-specific fields ----------


def validate_line_frequency_fields(
    *,
    frequency: str,
    start_ym: Optional[int],
    end_ym: Optional[int],
    one_time_ym: Optional[int],
) -> None:
    """
    Validate field combos by frequency.
    - monthly: require start_ym; allow end_ym >= start_ym; forbid one_time_ym
    - one_time: require one_time_ym; forbid start_ym and end_ym
    """
    freq = (frequency or "").lower()

    if freq == "monthly":
        if start_ym is None:
            raise ValueError("start_ym required for monthly")
        if end_ym is not None and end_ym < start_ym:
            raise ValueError("end_ym must be >= start_ym")
        if one_time_ym is not None:
            raise ValueError("one_time_ym must be empty for monthly")
        return

    if freq == "one_time":
        if one_time_ym is None:
            raise ValueError("one_time_ym required for one_time")
        if start_ym is not None or end_ym is not None:
            raise ValueError("start_ym/end_ym must be empty for one_time")
        return

    raise ValueError("frequency must be 'monthly' or 'one_time'")
