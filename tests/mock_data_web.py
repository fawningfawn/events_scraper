"""Mock data for testing web interface with real-looking events"""

from datetime import date
from datetime import timedelta


def get_sample_events():
    """Get sample events for testing"""
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    # Create mock events that look realistic
    events = []

    # Today's events with different times
    class MockEvent:
        def __init__(self, title, venue, date_str, time_str=None):
            self.title = title
            self.venue = venue
            self.date = date_str
            self.time = time_str
            self.is_past = False
            self.formatted_time = None

    # Past events (yesterday)
    events.append(
        MockEvent("Jazz Concert", "Blue Note", yesterday.strftime("%Y-%m-%d"), "20:30")
    )
    events.append(
        MockEvent(
            "Art Exhibition Opening",
            "Gallery Modern",
            yesterday.strftime("%Y-%m-%d"),
            None,
        )
    )

    # Today's events - mix of times
    events.append(
        MockEvent(
            "Morning Coffee Talk", "Café Central", today.strftime("%Y-%m-%d"), "09:30"
        )
    )
    events.append(
        MockEvent(
            "Lunch Networking", "Business Center", today.strftime("%Y-%m-%d"), "12:00"
        )
    )
    events.append(
        MockEvent("Evening Concert", "Music Hall", today.strftime("%Y-%m-%d"), "19:30")
    )
    events.append(
        MockEvent(
            "Late Night DJ Set", "Club Underground", today.strftime("%Y-%m-%d"), "23:00"
        )
    )
    events.append(
        MockEvent(
            "All Day Conference", "Convention Center", today.strftime("%Y-%m-%d"), None
        )
    )

    # Future events (tomorrow)
    events.append(
        MockEvent(
            "Morning Yoga", "Wellness Studio", tomorrow.strftime("%Y-%m-%d"), "07:00"
        )
    )
    events.append(
        MockEvent(
            "Business Meeting", "Office Tower", tomorrow.strftime("%Y-%m-%d"), "14:30"
        )
    )

    return events


def get_empty_events():
    """Get empty event list for testing no-events scenarios"""
    return []


def get_events_with_various_time_formats():
    """Get events with different time formats for parsing tests"""
    today = date.today()

    class MockEvent:
        def __init__(self, title, venue, date_str, time_str=None):
            self.title = title
            self.venue = venue
            self.date = date_str
            self.time = time_str
            self.is_past = False
            self.formatted_time = None

    events = []
    events.append(
        MockEvent("Event with HH:MM", "Venue 1", today.strftime("%Y-%m-%d"), "19:30")
    )
    events.append(
        MockEvent(
            "Event with HH:MM:SS", "Venue 2", today.strftime("%Y-%m-%d"), "19:30:45"
        )
    )
    events.append(
        MockEvent("Event with AM/PM", "Venue 3", today.strftime("%Y-%m-%d"), "7:30 PM")
    )
    events.append(
        MockEvent(
            "Event with AM/PM seconds",
            "Venue 4",
            today.strftime("%Y-%m-%d"),
            "7:30:45 PM",
        )
    )
    events.append(
        MockEvent("All day event", "Venue 5", today.strftime("%Y-%m-%d"), None)
    )

    return events
