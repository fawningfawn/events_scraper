"""
Utility functions for time parsing and date handling
"""

import logging
import re
from datetime import date
from datetime import time
from typing import Optional
from typing import Tuple
from typing import Union

import dateparser
import daterangeparser

logger = logging.getLogger(__name__)


def parse_time_string(time_str: str) -> Union[time, str]:
    """Parse time string to datetime.time object or return original string if unparseable.

    Args:
        time_str: Time string like "14:30", "9:00", "All day", etc.

    Returns:
        datetime.time object if parseable, original string otherwise
    """
    if not time_str or not time_str.strip():
        return None

    cleaned = time_str.strip()

    # Try HH:MM format first (most common)
    result = _try_parse_hh_mm_format(cleaned)
    if result is not None:
        return result

    # Try HH format (single hour)
    result = _try_parse_hh_format(cleaned)
    if result is not None:
        return result

    # If neither format works, return original string for display
    return cleaned


def _try_parse_hh_mm_format(cleaned: str) -> Union[time, None]:
    """Try to parse HH:MM format time strings"""
    hh_mm_pattern = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*Uhr)?$")
    match = hh_mm_pattern.match(cleaned)

    if match:
        try:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        except ValueError:
            pass

    return None


def _try_parse_hh_format(cleaned: str) -> Union[time, None]:
    """Try to parse single hour format like '14' or '9'"""
    hh_pattern = re.compile(r"^(\d{1,2})(?:\s*Uhr)?$")
    match = hh_pattern.match(cleaned)

    if match:
        try:
            hour = int(match.group(1))
            if 0 <= hour <= 23:
                return time(hour, 0)
        except ValueError:
            pass

    return None


def parse_day_month_with_reference_year(
    day_month_text: str, reference_date: date, rollover_days: int = 180
) -> Optional[date]:
    """
    Parse day/month text like "02.08" with year inferred from reference date.

    Uses reference year first, then adjusts +/- 1 year when date is far away.
    """
    if not day_month_text or "." not in day_month_text:
        return None
    try:
        day_text, month_text = day_month_text.strip().split(".")
        candidate = date(
            reference_date.year,
            int(month_text),
            int(day_text),
        )
    except ValueError:
        return None

    if (reference_date - candidate).days > rollover_days:
        return date(reference_date.year + 1, candidate.month, candidate.day)
    if (candidate - reference_date).days > rollover_days:
        return date(reference_date.year - 1, candidate.month, candidate.day)
    return candidate


def parse_date_range(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Parse date range strings into start and end dates.

    Handles various formats:
    - "Jul 25 ~ Jul 29" (Hong Kong Cheapo format)
    - "4-8th May" (DateRangeParser format)
    - "Aug 1 - Aug 3" (dash separator)
    - "Sat, Sep 06" (single date)
    - "December 3-5, Venue, Location" (date with location suffix)
    - "(April 25-27, 2026)" (date in parentheses)

    Args:
        date_str: Date string to parse

    Returns:
        Tuple of (start_date, end_date). For single dates, end_date is None.
        Both are None if parsing fails.
    """
    if not date_str or not date_str.strip():
        return None, None

    date_str = date_str.strip()
    logger.debug(f"Parsing date range: '{date_str}'")

    # Skip unconfirmed dates
    if _is_unconfirmed_date(date_str):
        logger.debug(f"Skipping unconfirmed date: {date_str}")
        return None, None

    # Clean date string (remove parentheses, extract date before location info)
    cleaned = _clean_date_string(date_str)
    if cleaned != date_str:
        logger.debug(f"Cleaned date string: '{cleaned}'")

    # Try DateRangeParser first
    result = _try_daterangeparser(cleaned)
    if result != (None, None):
        return result

    # Try manual parsing formats
    result = _try_manual_parsing(cleaned)
    if result != (None, None):
        return result

    # Try single date parsing
    return _try_single_date_parsing(cleaned)


def _clean_date_string(date_str: str) -> str:  # noqa: C901
    """
    Clean date string by removing common non-date content and injecting year from context.

    Handles:
    - Parentheses: "(April 25-27, 2026)" -> "April 25-27, 2026"
    - Location suffixes: "December 3-5, Venue, City" -> "December 3-5"
    - Year extraction: "BFF'26 | June 4-7" -> "June 4-7, 2026"
    - Year injection: "FilmFest 2026 on June 4-7" -> "June 4-7, 2026"
    - Embedded dates: "Event on June 4-7 in Warsaw" -> "June 4-7"
    """

    # Extract year from string context before cleaning
    extracted_year = _extract_year_from_context(date_str)

    # Normalize various dash characters to ASCII hyphen for consistent parsing
    date_str = date_str.replace("—", "-")  # em-dash
    date_str = date_str.replace("–", "-")  # en-dash
    date_str = date_str.replace("\u2014", "-")  # em-dash unicode
    date_str = date_str.replace("\u2013", "-")  # en-dash unicode
    # Handle malformed UTF-8 sequences
    date_str = date_str.replace("â\x80\x94", "-")
    date_str = date_str.replace('â€"', "-")

    # Handle "Location | Month Year" format (e.g., "Austin | May 2025")
    if "|" in date_str:
        parts = date_str.split("|")
        if len(parts) == 2:
            date_str = parts[1].strip()

    # Remove parentheses
    if date_str.startswith("(") and date_str.endswith(")"):
        date_str = date_str[1:-1]

    # Try to find date pattern anywhere in the string
    # Patterns: "Month Day-Day" or "Month Day-Day, Year" or "Day - Day Month"
    # First try: Spanish "2, 3 y 4 de octubre de 2026" format
    # Extract first and last day, convert to range format
    if match := re.search(
        r"\b(\d{1,2})(?:,\s*\d{1,2})*\s*y\s*(\d{1,2})\s+de\s+([A-Za-z]+)\s+de\s+(\d{4})\b",
        date_str,
        re.IGNORECASE,
    ):
        first_day, last_day, month, year = match.groups()
        date_str = f"{first_day}-{last_day} {month} {year}"
    # Second try: Day-Dayth of Month format (e.g., "24-25th of January")
    elif match := re.search(
        r"\b(\d{1,2}(?:st|nd|rd|th)?-\d{1,2}(?:st|nd|rd|th)?\s+of\s+[A-Z][a-z]+)\b",
        date_str,
        re.IGNORECASE,
    ):
        date_str = match.group(1).strip()
    # Second try: Month Day-Day format (supports regular dash and em-dash)
    # Generic word pattern - no hardcoded month names
    # Supports ordinal suffixes: "February 9th - 13th"
    # Validation happens downstream via dateparser
    elif match := re.search(
        r"\b([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s*[—\-]\s*\d{1,2}(?:st|nd|rd|th)?)\b",
        date_str,
        re.IGNORECASE,
    ):
        date_str = match.group(1).strip()
    # Third try: Day - Day Month format (e.g., "14 - 15 NOVEMBER")
    # Now that dashes are normalized, use simple hyphen pattern
    elif match := re.search(r"\b(\d{1,2}\s*-\s*\d{1,2}\s+[A-Z][a-z]+)\b", date_str):
        date_str = match.group(1).strip()
    else:
        # If no embedded date found, try to extract from start
        # Patterns: "Month Day-Day" or "Month Day-Day, Year"
        # Stop at comma followed by non-numeric content (location names)
        match = re.match(r"^([A-Za-z]+ \d+-\d+(?:,? \d{4})?)", date_str)
        if match:
            potential_date = match.group(1).strip()
            # If we have content after this
            remainder = date_str[len(potential_date) :].strip()
            if remainder.startswith(",") and not remainder[1:].strip()[:4].isdigit():
                # Comma followed by non-year content (likely location)
                date_str = potential_date

    # If we extracted a year and the date string doesn't already have a year, append it
    if extracted_year and not _date_has_year(date_str):
        date_str = f"{date_str}, {extracted_year}"

    return date_str


def _extract_year_from_context(text: str) -> Optional[int]:
    """
    Extract year from string context.

    Handles:
    - 4-digit years: 2025, 2026, 2027
    - Abbreviated years: '25, '26, '27 -> 2025, 2026, 2027
    - Multiple years: use first one >= 2024

    Args:
        text: Full text string that may contain year information

    Returns:
        Extracted year as integer, or None if no valid year found
    """
    # Look for abbreviated year patterns like '26, '27
    abbreviated_pattern = r"'(\d{2})\b"
    abbreviated_matches = re.findall(abbreviated_pattern, text)
    for year_suffix in abbreviated_matches:
        year = 2000 + int(year_suffix)
        if year >= 2024:  # Only accept years from 2024 onwards
            return year

    # Look for 4-digit years
    four_digit_pattern = r"\b(20\d{2})\b"
    four_digit_matches = re.findall(four_digit_pattern, text)
    for year_str in four_digit_matches:
        year = int(year_str)
        if year >= 2024:  # Only accept years from 2024 onwards
            return year

    return None


def _date_has_year(date_str: str) -> bool:
    """
    Check if date string already contains a year.

    Args:
        date_str: Date string to check

    Returns:
        True if date string contains a 4-digit year
    """
    return bool(re.search(r"\b20\d{2}\b", date_str))


def _is_unconfirmed_date(date_str: str) -> bool:
    """Check if date string represents an unconfirmed date"""
    return any(
        word in date_str.lower() for word in ["early", "mid", "late", "unconfirmed"]
    )


def _try_daterangeparser(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Try parsing with DateRangeParser library"""
    try:
        result = daterangeparser.parse(date_str)
        if result and len(result) >= 1:
            start_date = result[0].date() if result[0] else None
            end_date = result[1].date() if len(result) > 1 and result[1] else None

            if start_date:
                logger.debug(f"DateRangeParser success: {start_date} to {end_date}")
                return start_date, end_date
    except Exception as e:
        logger.debug(f"DateRangeParser failed: {e}")
    return None, None


def _try_manual_parsing(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Try manual parsing for specific formats"""
    if "~" in date_str:
        return _parse_tilde_format(date_str)
    if " - " in date_str:
        return _parse_dash_format(date_str)
    return None, None


def _try_single_date_parsing(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Try parsing as single date"""
    try:
        parsed_date = dateparser.parse(date_str)
        if parsed_date:
            single_date = parsed_date.date()
            logger.debug(f"Single date parsed: {single_date}")
            return single_date, None
    except Exception as e:
        logger.debug(f"Dateparser failed: {e}")

    logger.warning(f"Could not parse date string: '{date_str}'")
    return None, None


def _parse_tilde_format(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Parse Hong Kong Cheapo tilde format: 'Jul 25 ~ Jul 29'"""
    try:
        parts = [part.strip() for part in date_str.split("~")]
        if len(parts) != 2:
            return None, None

        start_str, end_str = parts

        # Parse start date
        start_date = dateparser.parse(start_str)
        if not start_date:
            return None, None

        # For end date, if it's just a number, assume same month/year as start
        if end_str.isdigit():
            end_str = f"{start_date.strftime('%b')} {end_str} {start_date.year}"

        end_date = dateparser.parse(end_str)

        if start_date and end_date:
            logger.debug(
                f"Tilde format parsed: {start_date.date()} to {end_date.date()}"
            )
            return start_date.date(), end_date.date()

    except Exception as e:
        logger.debug(f"Tilde format parsing failed: {e}")

    return None, None


def _parse_dash_format(date_str: str) -> Tuple[Optional[date], Optional[date]]:
    """Parse dash format: 'Aug 1 - Aug 3'"""
    try:
        parts = [part.strip() for part in date_str.split(" - ")]
        if len(parts) != 2:
            return None, None

        start_str, end_str = parts

        start_date = dateparser.parse(start_str)
        end_date = dateparser.parse(end_str)

        if start_date and end_date:
            logger.debug(f"Dash format parsed: {start_date.date()} to {end_date.date()}")
            return start_date.date(), end_date.date()

    except Exception as e:
        logger.debug(f"Dash format parsing failed: {e}")

    return None, None
