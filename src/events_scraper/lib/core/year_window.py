"""Shared rolling year-window helpers for runtime filtering and status views."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional


def get_year_window(
    *,
    current_year: Optional[int] = None,
    past_years: int = 1,
    future_years: int = 1,
    config=None,
) -> tuple[int, int]:
    """Return inclusive year window `(start_year, end_year)`."""
    base_year = current_year or date.today().year

    config_past = _coerce_int(
        config._config_data.get("year_window_past") if config is not None else None,
        past_years,
    )
    config_future = _coerce_int(
        config._config_data.get("year_window_future") if config is not None else None,
        future_years,
    )

    start_year = base_year - max(config_past, 0)
    end_year = base_year + max(config_future, 0)
    return start_year, end_year


def get_target_years(
    *,
    current_year: Optional[int] = None,
    past_years: int = 0,
    future_years: int = 1,
    config=None,
) -> list[int]:
    """Return sorted year list for status/report views."""
    start_year, end_year = get_year_window(
        current_year=current_year,
        past_years=past_years,
        future_years=future_years,
        config=config,
    )
    return list(range(start_year, end_year + 1))


def is_year_in_window(
    date_str: str,
    *,
    current_year: Optional[int] = None,
    past_years: int = 1,
    future_years: int = 1,
    config=None,
) -> bool:
    """Check whether any year in `date_str` falls inside configured window."""
    years = [int(year) for year in re.findall(r"20\d{2}", date_str)]
    if not years:
        return False

    start_year, end_year = get_year_window(
        current_year=current_year,
        past_years=past_years,
        future_years=future_years,
        config=config,
    )
    return any(start_year <= year <= end_year for year in years)


def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)
