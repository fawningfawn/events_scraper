"""Shared runtime execution for scrapers."""

from __future__ import annotations

from dataclasses import dataclass

from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.packages import load_packages


@dataclass
class ScrapeResult:
    scraper_name: str
    url: str
    scraped_count: int
    saved_count: int
    http_status: int
    error_message: str | None


def resolve_scraper(scraper_name: str, target_url: str | None = None):
    for pkg in load_packages():
        for scraper in pkg.load_scrapers():
            if scraper.scraper_name != scraper_name:
                continue
            if target_url and getattr(scraper, "url", None) != target_url:
                continue
            return scraper
    return None


def run_scraper(
    scraper_name: str,
    target_url: str | None = None,
    *,
    save: bool = True,
) -> ScrapeResult:
    scraper = resolve_scraper(scraper_name, target_url=target_url)
    if scraper is None:
        if target_url:
            raise ValueError(f"Scraper {scraper_name} with url {target_url} not found")
        raise ValueError(f"Scraper {scraper_name} not found")

    collection = scraper.fetch()
    events = collection.to_list() if hasattr(collection, "to_list") else list(collection)
    scraped_count = len(events)
    saved_count = 0

    if save:
        for event in events:
            try:
                event.scraper = scraper.scraper_name
                if event.save():
                    saved_count += 1
            except Exception:
                continue

    http_status, error_message = get_scraper_http_status(
        scraper_name=scraper.scraper_name,
        target_url=scraper.url,
    )
    return ScrapeResult(
        scraper_name=scraper.scraper_name,
        url=scraper.url,
        scraped_count=scraped_count,
        saved_count=saved_count,
        http_status=http_status,
        error_message=error_message,
    )


def get_scraper_http_status(
    scraper_name: str,
    target_url: str | None = None,
) -> tuple[int, str | None]:
    session = get_session()
    try:
        query = session.query(ScraperStatus).filter_by(scraper_name=scraper_name)
        if target_url:
            query = query.filter_by(url=target_url)
        latest_status = query.order_by(ScraperStatus.timestamp.desc()).first()
        http_status = latest_status.status_code if latest_status else 200
        error_message = latest_status.error_message if latest_status else None
        return http_status, error_message
    finally:
        session.close()
