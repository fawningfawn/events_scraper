"""
Config processing utilities for AI scrapers.

Handles variable expansion in URLs (e.g., {year}, {yy}).
"""

from datetime import date
from typing import List
from typing import Optional


def expand_url_variables(url: str, date_range: Optional[tuple] = None) -> List[str]:
    """
    Expand {year} and {yy} variables in URLs.

    Args:
        url: URL possibly containing {year} or {yy}
        date_range: Optional tuple of (start_date, end_date). If None, defaults to
                    current year + next year (2 total years)

    Returns:
        List of expanded URLs (or single-element list if no variables)

    Example:
        expand_url_variables("https://example.com/{year}/", None)
        # Returns: ["https://example.com/2025/", "https://example.com/2026/"]

        expand_url_variables("https://example.com/{yy}/",
                           (date(2025,1,1), date(2027,12,31)))
        # Returns: ["https://example.com/25/", ".../26/", ".../27/"]
    """
    # Check if URL contains year variables
    if "{year}" not in url and "{yy}" not in url:
        return [url]

    # Determine year range
    if date_range is None:
        # Default: current year + next year
        current_year = date.today().year
        years = range(current_year, current_year + 2)
    else:
        # Extract year range from date_range tuple
        start_date, end_date = date_range
        years = range(start_date.year, end_date.year + 1)

    # Expand URL for each year
    expanded_urls = []
    for year in years:
        expanded_url = url.replace("{year}", str(year))
        expanded_url = expanded_url.replace("{yy}", str(year)[-2:])
        expanded_urls.append(expanded_url)

    return expanded_urls
