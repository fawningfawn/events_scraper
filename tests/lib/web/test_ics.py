"""Tests for ICS calendar feed generation"""

import unittest
from datetime import date
from datetime import time

from icalendar import Calendar

from events_scraper.lib import mock_data
from events_scraper.lib.web.ics import events_to_ical


class IcsGenerationTestCase(unittest.TestCase):
    """Test ICS feed generation from Event objects"""

    def test_empty_event_list_returns_valid_vcalendar(self):
        """Empty list should return a valid VCALENDAR with no VEVENTs"""
        result = events_to_ical([])
        cal = Calendar.from_ical(result)
        self.assertEqual(cal["PRODID"], "-//Events Scraper//EN")
        self.assertEqual(cal["VERSION"], "2.0")
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(vevents), 0)

    def test_single_event_produces_vevent(self):
        """A single event should produce one VEVENT"""
        event = mock_data.get_event(
            title="Test Concert",
            date=date(2026, 4, 15),
            time=time(20, 0),
            location="Main Hall",
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(vevents), 1)

    def test_required_fields_present(self):
        """Each VEVENT must have UID, DTSTAMP, DTSTART, SUMMARY"""
        event = mock_data.get_event(
            title="Required Fields Test",
            date=date(2026, 5, 1),
            time=time(19, 30),
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertIn("UID", vevent)
        self.assertIn("DTSTAMP", vevent)
        self.assertIn("DTSTART", vevent)
        self.assertIn("SUMMARY", vevent)

    def test_summary_matches_title(self):
        """SUMMARY should match the event title"""
        event = mock_data.get_event(title="My Event Title", date=date(2026, 6, 1))
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertEqual(str(vevent["SUMMARY"]), "My Event Title")

    def test_timed_event_has_dtstart_with_time(self):
        """An event with a time should have a datetime DTSTART"""
        event = mock_data.get_event(
            date=date(2026, 7, 10),
            time=time(14, 30),
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        dtstart = vevent["DTSTART"].dt
        self.assertEqual(dtstart.year, 2026)
        self.assertEqual(dtstart.month, 7)
        self.assertEqual(dtstart.day, 10)
        self.assertEqual(dtstart.hour, 14)
        self.assertEqual(dtstart.minute, 30)

    def test_allday_event_has_date_dtstart(self):
        """An event without a time should be an all-day event with a date DTSTART"""
        event = mock_data.get_event(
            date=date(2026, 8, 5),
            time=None,
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        dtstart = vevent["DTSTART"].dt
        # All-day events should have a date, not datetime
        self.assertIsInstance(dtstart, date)
        self.assertNotIsInstance(dtstart, type(None))
        self.assertEqual(dtstart, date(2026, 8, 5))

    def test_multiday_event_has_dtend(self):
        """An event with end_date should have DTEND set"""
        event = mock_data.get_event(
            date=date(2026, 9, 1),
            end_date=date(2026, 9, 3),
            time=None,
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertIn("DTEND", vevent)
        # All-day DTEND is exclusive, so 9/3 means last day is 9/3
        dtend = vevent["DTEND"].dt
        self.assertEqual(dtend, date(2026, 9, 4))

    def test_stable_uid_from_event_id(self):
        """UID should be stable and derived from event.id"""
        event1 = mock_data.get_event(id=42, date=date(2026, 1, 1))
        event2 = mock_data.get_event(id=42, date=date(2026, 1, 1))
        result1 = events_to_ical([event1])
        result2 = events_to_ical([event2])
        cal1 = Calendar.from_ical(result1)
        cal2 = Calendar.from_ical(result2)
        uid1 = str([c for c in cal1.walk() if c.name == "VEVENT"][0]["UID"])
        uid2 = str([c for c in cal2.walk() if c.name == "VEVENT"][0]["UID"])
        self.assertEqual(uid1, uid2)

    def test_different_events_have_different_uids(self):
        """Different event IDs should produce different UIDs"""
        event1 = mock_data.get_event(id=1, date=date(2026, 1, 1))
        event2 = mock_data.get_event(id=2, date=date(2026, 1, 1))
        result = events_to_ical([event1, event2])
        cal = Calendar.from_ical(result)
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]
        uids = {str(v["UID"]) for v in vevents}
        self.assertEqual(len(uids), 2)

    def test_location_included_when_present(self):
        """LOCATION should be set when event has a location"""
        event = mock_data.get_event(
            date=date(2026, 1, 1),
            location="Concert Hall",
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertEqual(str(vevent["LOCATION"]), "Concert Hall")

    def test_location_absent_when_none(self):
        """LOCATION should not be set when event has no location"""
        event = mock_data.get_event(
            date=date(2026, 1, 1),
            location=None,
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertNotIn("LOCATION", vevent)

    def test_url_included(self):
        """URL should be set from event detail_url"""
        event = mock_data.get_event(
            date=date(2026, 1, 1),
            detail_url="https://example.com/event/1",
        )
        result = events_to_ical([event])
        cal = Calendar.from_ical(result)
        vevent = [c for c in cal.walk() if c.name == "VEVENT"][0]
        self.assertEqual(str(vevent["URL"]), "https://example.com/event/1")

    def test_multiple_events(self):
        """Multiple events should produce multiple VEVENTs"""
        events = [mock_data.get_event(id=i, date=date(2026, 1, i + 1)) for i in range(5)]
        result = events_to_ical(events)
        cal = Calendar.from_ical(result)
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]
        self.assertEqual(len(vevents), 5)

    def test_output_is_bytes(self):
        """Output should be bytes for HTTP response"""
        result = events_to_ical([])
        self.assertIsInstance(result, bytes)

    def test_content_type_compatible(self):
        """Output should be valid UTF-8 text/calendar content"""
        event = mock_data.get_event(date=date(2026, 1, 1), title="Über Cool")
        result = events_to_ical([event])
        text = result.decode("utf-8")
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("BEGIN:VEVENT", text)
        self.assertIn("END:VCALENDAR", text)
