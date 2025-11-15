# app/period_ym.py
# Purpose: handle "month without day" as an integer YYYYMM (e.g., 202501).
# UI can show/accept "MM/YY" (e.g., "01/25") and we convert both ways.

from typing import Optional, Tuple


def parse_mm_yy(text: str) -> int:
    """
    Convert 'MM/YY' or 'MM/YYYY' to YYYYMM.
    - Strips spaces
    - Accepts '01/25' -> 202501, '12/2026' -> 202612
    - Raises ValueError on bad input
    """
    s = text.strip()
    if "/" not in s:
        raise ValueError("Expected 'MM/YY' or 'MM/YYYY'")
    mm_str, yy_str = [p.strip() for p in s.split("/", 1)]

    # month must be 1..12
    if not mm_str.isdigit():
        raise ValueError("Month must be digits")
    mm = int(mm_str)
    if mm < 1 or mm > 12:
        raise ValueError("Month out of range (1-12)")

    # year can be '25' or '2025'
    if not yy_str.isdigit():
        raise ValueError("Year must be digits")
    if len(yy_str) == 2:
        # Interpret two-digit years as 2000..2099
        yy = 2000 + int(yy_str)
    elif len(yy_str) == 4:
        yy = int(yy_str)
    else:
        raise ValueError("Year must be 2 or 4 digits")

    return yy * 100 + mm  # YYYYMM


def format_ym(ym: int) -> str:
    """
    Convert YYYYMM integer -> 'MM/YY' string (01/25).
    """
    year, month = to_year_month(ym)
    return f"{month:02d}/{year % 100:02d}"


def to_year_month(ym: int) -> Tuple[int, int]:
    """
    Split YYYYMM -> (YYYY, MM). Raises ValueError if malformed.
    """
    if ym < 10000:  # minimal sensible value is 100001 (year 1000)
        raise ValueError("YYYYMM is too small")
    year = ym // 100
    month = ym % 100
    if month < 1 or month > 12:
        raise ValueError("Invalid month in YYYYMM")
    return year, month


def in_range(ym: int, start_ym: Optional[int], end_ym: Optional[int]) -> bool:
    """
    True if ym is within [start_ym, end_ym].
    - None start means open (-∞)
    - None end means open (+∞)
    """
    if start_ym is not None and ym < start_ym:
        return False
    if end_ym is not None and ym > end_ym:
        return False
    return True


def validate_line_frequency_fields(
    *,
    frequency: str,
    start_ym: Optional[int],
    end_ym: Optional[int],
    one_time_ym: Optional[int],
) -> None:
    """
    Enforce field combos:
    - monthly: start_ym required; end_ym optional; one_time_ym must be None
    - one_time: one_time_ym required; start_ym/end_ym must be None
    Raises ValueError on violations.
    """
    if frequency == "monthly":
        if start_ym is None:
            raise ValueError("monthly requires start_ym")
        if one_time_ym is not None:
            raise ValueError("monthly must not set one_time_ym")
    elif frequency == "one_time":
        if one_time_ym is None:
            raise ValueError("one_time requires one_time_ym")
        if start_ym is not None or end_ym is not None:
            raise ValueError("one_time must not set start_ym/end_ym")
    else:
        raise ValueError("frequency must be 'monthly' or 'one_time'")
