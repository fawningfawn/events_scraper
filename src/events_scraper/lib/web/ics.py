"""ICS calendar feed generation from Event objects."""

from datetime import datetime
from datetime import timedelta
from typing import List
from zoneinfo import ZoneInfo

from icalendar import Calendar
from icalendar import Event as ICalEvent

from events_scraper.lib.core import Event

LOCAL_TZ = ZoneInfo("Europe/Paris")


def events_to_ical(events: List[Event], name: str = "Events") -> bytes:
    """Convert a list of Event objects to a valid iCalendar feed."""
    cal = Calendar()
    cal.add("PRODID", "-//Events Scraper//EN")
    cal.add("VERSION", "2.0")
    cal.add("X-WR-CALNAME", name)

    for event in events:
        cal.add_component(_event_to_vevent(event))

    return cal.to_ical()


def _event_to_vevent(event: Event) -> ICalEvent:
    """Convert a single Event to a VEVENT component."""
    vevent = ICalEvent()

    vevent.add("UID", f"event-{event.id}@events-scraper")
    vevent.add("DTSTAMP", datetime.now(tz=LOCAL_TZ))
    vevent.add("SUMMARY", event.title)

    if event.time:
        hour = (
            event.time.hour
            if hasattr(event.time, "hour")
            else int(event.time.split(":")[0])
        )
        minute = (
            event.time.minute
            if hasattr(event.time, "minute")
            else int(event.time.split(":")[1])
        )
        dtstart = datetime(
            event.date.year,
            event.date.month,
            event.date.day,
            hour,
            minute,
            tzinfo=LOCAL_TZ,
        )
        vevent.add("DTSTART", dtstart)
    else:
        vevent.add("DTSTART", event.date)

    if event.end_date:
        if event.time:
            vevent.add(
                "DTEND",
                datetime(
                    event.end_date.year,
                    event.end_date.month,
                    event.end_date.day,
                    tzinfo=LOCAL_TZ,
                ),
            )
        else:
            # All-day DTEND is exclusive in iCal spec
            vevent.add("DTEND", event.end_date + timedelta(days=1))

    if event.location:
        vevent.add("LOCATION", event.location)

    if event.detail_url:
        vevent.add("URL", event.detail_url)

    return vevent
