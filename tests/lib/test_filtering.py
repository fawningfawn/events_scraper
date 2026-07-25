#!/usr/bin/env python3
"""
Unit tests for event filtering functionality
"""

import re
import unittest

from events_scraper.lib import mock_data
from events_scraper.lib.core import Event
from events_scraper.lib.core import EventCollection


class TestEventCollectionFiltering(unittest.TestCase):
    """Test filtering methods in EventCollection"""

    def setUp(self):
        """Set up test events"""
        # Create completely random events for filtering tests
        self.events = [
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
        ]

        self.collection = EventCollection(self.events)

    def test_exclude_categories_string(self):
        """Test category exclusion with exact match"""
        # Get the first event's first category for exact match testing
        if self.events and self.events[0].categories:
            test_category = self.events[0].categories[0]

            # Find events that have this exact category
            events_with_cat = [e for e in self.events if test_category in e.categories]
            events_without_cat = [
                e for e in self.events if test_category not in e.categories
            ]

            # Filter out events with this exact category
            filtered = self.collection.exclude_categories([test_category])
            filtered_events = filtered.to_list()

            # Should exclude events that have this exact category
            self.assertEqual(len(filtered_events), len(events_without_cat))
            filtered_titles = [e.title for e in filtered_events]

            # Verify excluded events are not in results
            for event in events_with_cat:
                self.assertNotIn(event.title, filtered_titles)

            # Verify non-excluded events are in results
            for event in events_without_cat:
                self.assertIn(event.title, filtered_titles)

    def test_exclude_categories_regex(self):
        """Test category exclusion with compiled regex patterns"""
        # Test regex pattern that excludes categories ending with specific letters
        test_pattern = re.compile(".*e$", re.IGNORECASE)  # Categories ending with "e"
        events_with_e_ending = [
            e
            for e in self.events
            if any(test_pattern.search(cat) for cat in e.categories)
        ]
        events_without_e_ending = [
            e
            for e in self.events
            if not any(test_pattern.search(cat) for cat in e.categories)
        ]

        filtered = self.collection.exclude_categories([test_pattern])
        filtered_events = filtered.to_list()

        # Should exclude events with categories ending in "e"
        self.assertEqual(len(filtered_events), len(events_without_e_ending))
        filtered_titles = [e.title for e in filtered_events]

        # Verify excluded events are not in results
        for event in events_with_e_ending:
            self.assertNotIn(event.title, filtered_titles)

        # Verify non-excluded events are in results
        for event in events_without_e_ending:
            self.assertIn(event.title, filtered_titles)

    def test_include_categories_string(self):
        """Test category inclusion with exact match"""
        # Use first event's first category for exact match testing
        if self.events and self.events[0].categories:
            test_category = self.events[0].categories[0]
            events_with_cat = [e for e in self.events if test_category in e.categories]

            filtered = self.collection.include_categories([test_category])
            filtered_events = filtered.to_list()

            # Should include only events with this exact category
            self.assertEqual(len(filtered_events), len(events_with_cat))
            filtered_titles = [e.title for e in filtered_events]

            # Verify all included events have the expected category
            for event in events_with_cat:
                self.assertIn(event.title, filtered_titles)

            # Verify excluded events are not in results
            events_without_cat = [
                e for e in self.events if test_category not in e.categories
            ]
            for event in events_without_cat:
                self.assertNotIn(event.title, filtered_titles)

    def test_include_categories_regex(self):
        """Test category inclusion with compiled regex patterns"""
        # Test regex pattern that includes categories starting with specific letters
        test_pattern = re.compile("^[A-C].*", re.IGNORECASE)  # Compiled pattern
        events_matching_pattern = [
            e
            for e in self.events
            if any(test_pattern.search(cat) for cat in e.categories)
        ]

        filtered = self.collection.include_categories([test_pattern])
        filtered_events = filtered.to_list()

        # Should include only events with categories starting with A, B, or C
        self.assertEqual(len(filtered_events), len(events_matching_pattern))
        filtered_titles = [e.title for e in filtered_events]

        # Verify all matching events are included
        for event in events_matching_pattern:
            self.assertIn(event.title, filtered_titles)

        # Verify non-matching events are excluded
        events_not_matching = [
            e for e in self.events if e not in events_matching_pattern
        ]
        for event in events_not_matching:
            self.assertNotIn(event.title, filtered_titles)

    def test_exclude_titles_string(self):
        """Test title exclusion with string matching"""
        # Use the first letter of the first event's title as test string
        if self.events and self.events[0].title:
            test_string = self.events[0].title[0].lower()
            events_with_letter = [
                e for e in self.events if test_string.lower() in e.title.lower()
            ]
            events_without_letter = [
                e for e in self.events if test_string.lower() not in e.title.lower()
            ]

            filtered = self.collection.exclude_titles([test_string])
            filtered_events = filtered.to_list()

            # Should exclude events with the test letter in title
            self.assertEqual(len(filtered_events), len(events_without_letter))
            filtered_titles = [e.title for e in filtered_events]

            # Verify excluded events are not in results
            for event in events_with_letter:
                self.assertNotIn(event.title, filtered_titles)

            # Verify non-excluded events are in results
            for event in events_without_letter:
                self.assertIn(event.title, filtered_titles)
        else:
            # Skip test if no events or empty titles
            self.skipTest("No events with titles to test")

    def test_exclude_titles_regex(self):
        """Test title exclusion with regex patterns (automatic fallback)"""
        # Test excluding titles that start with vowels
        test_pattern = "^[AEIOUaeiou].*"
        events_starting_with_vowel = [
            e for e in self.events if e.title and e.title[0].upper() in "AEIOU"
        ]
        events_not_starting_with_vowel = [
            e for e in self.events if e.title and e.title[0].upper() not in "AEIOU"
        ]

        filtered = self.collection.exclude_titles([test_pattern])
        filtered_events = filtered.to_list()

        # Should exclude events with titles starting with vowels
        self.assertEqual(len(filtered_events), len(events_not_starting_with_vowel))
        filtered_titles = [e.title for e in filtered_events]

        # Verify excluded events are not in results
        for event in events_starting_with_vowel:
            self.assertNotIn(event.title, filtered_titles)

        # Verify non-excluded events are in results
        for event in events_not_starting_with_vowel:
            self.assertIn(event.title, filtered_titles)

    def test_include_titles_string(self):
        """Test title inclusion with string matching"""
        # Use common letters that might appear in titles
        test_strings = ["a", "e"]  # Common letters likely to appear in titles

        filtered = self.collection.include_titles(test_strings)
        filtered_events = filtered.to_list()

        # Should include events with "a" or "e" in title
        [e.title for e in filtered_events]

        # Verify all included events have at least one of the test letters
        for event in filtered_events:
            has_letter = any(
                letter.lower() in event.title.lower() for letter in test_strings
            )
            self.assertTrue(
                has_letter, f"Event '{event.title}' should contain 'a' or 'e'"
            )

    def test_include_titles_regex(self):
        """Test title inclusion with regex patterns (automatic fallback)"""
        # Include titles that contain at least 2 consecutive vowels
        test_pattern = ".*[AEIOUaeiou]{2}.*"
        events_with_double_vowels = [
            e
            for e in self.events
            if any(
                e.title[i : i + 2].lower()
                in [
                    "aa",
                    "ae",
                    "ai",
                    "ao",
                    "au",
                    "ea",
                    "ee",
                    "ei",
                    "eo",
                    "eu",
                    "ia",
                    "ie",
                    "ii",
                    "io",
                    "iu",
                    "oa",
                    "oe",
                    "oi",
                    "oo",
                    "ou",
                    "ua",
                    "ue",
                    "ui",
                    "uo",
                    "uu",
                ]
                for i in range(len(e.title) - 1)
            )
            if e.title
        ]

        filtered = self.collection.include_titles([test_pattern])
        filtered_events = filtered.to_list()

        # Should include only events with consecutive vowels in title
        self.assertEqual(len(filtered_events), len(events_with_double_vowels))
        filtered_titles = [e.title for e in filtered_events]

        # Verify included events match the pattern
        for event in events_with_double_vowels:
            self.assertIn(event.title, filtered_titles)

    def test_chaining_filters(self):
        """Test chaining multiple filter operations"""
        # Use first event's category for testing
        if self.events and self.events[0].categories:
            test_category = self.events[0].categories[0]

            # Chain filters: include events with test_category, then exclude those with "e" in titles
            events_with_category = [
                e for e in self.events if test_category in e.categories
            ]
            events_with_category_but_not_e = [
                e for e in events_with_category if "e" not in e.title.lower()
            ]

            filtered = self.collection.include_categories(
                [test_category]
            ).exclude_titles(["e"])
            filtered_events = filtered.to_list()

            # Should match our manually calculated result
            self.assertEqual(len(filtered_events), len(events_with_category_but_not_e))

            # Verify the chaining worked correctly
            for event in filtered_events:
                # Should have test_category
                self.assertIn(test_category, event.categories)
                # Should NOT have "e" in title
                self.assertNotIn("e", event.title.lower())

    def test_mixed_string_and_regex_filters(self):
        """Test using both exact string and regex filters together"""
        # Use first event's first category as exact string filter
        if self.events and self.events[0].categories:
            exact_category = self.events[0].categories[0]

            # Regex filter for categories starting with consonants
            regex_filter = re.compile("^[BCDFGHJKLMNPQRSTVWXYZbcdfghjklmnpqrstvwxyz].*")

            events_to_exclude = [
                e
                for e in self.events
                if exact_category in e.categories
                or any(regex_filter.search(cat) for cat in e.categories)
            ]
            events_to_keep = [e for e in self.events if e not in events_to_exclude]

            filtered = self.collection.exclude_categories([exact_category, regex_filter])
            filtered_events = filtered.to_list()

            # Should exclude events matching either filter
            self.assertEqual(len(filtered_events), len(events_to_keep))
            filtered_titles = [e.title for e in filtered_events]

            # Verify excluded events are not in results
            for event in events_to_exclude:
                self.assertNotIn(event.title, filtered_titles)

            # Verify kept events are in results
            for event in events_to_keep:
                self.assertIn(event.title, filtered_titles)

    def test_case_insensitive_string_matching(self):
        """Test that string matching is case-insensitive"""
        # Test with various case combinations of "A"
        filtered1 = self.collection.include_categories(["A"])
        filtered2 = self.collection.include_categories(["a"])

        # All should return the same results (case-insensitive)
        results1 = filtered1.to_list()
        results2 = filtered2.to_list()

        self.assertEqual(len(results1), len(results2))

        # Verify same events are returned regardless of case
        titles1 = [e.title for e in results1]
        titles2 = [e.title for e in results2]
        self.assertEqual(set(titles1), set(titles2))

    def test_empty_filters(self):
        """Test behavior with empty filter lists"""
        # Empty exclude should return all events
        filtered = self.collection.exclude_categories([])
        self.assertEqual(len(filtered.to_list()), len(self.events))

        # Empty include should return all events (when no filters applied)
        filtered = self.collection.exclude_titles([])
        self.assertEqual(len(filtered.to_list()), len(self.events))

    def test_automatic_regex_fallback(self):
        """Test that regex patterns work automatically when string matching fails"""
        # This pattern won't match as substring but will match as regex
        filtered = self.collection.include_titles([".*Bewegung.*"])

        # Add a test event with "Bewegung" to verify the pattern works
        test_event = Event(
            title="Durch Bewegung zum Wohlgefühl - Nehmen Sie sich Zeit für sich selbst",
            date="2025-07-23",
            categories=["Health"],
        )
        test_collection = EventCollection(self.events + [test_event])

        # The regex pattern should match the German title
        filtered = test_collection.include_titles([".*Bewegung.*"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 1)
        self.assertEqual(
            filtered_events[0].title,
            "Durch Bewegung zum Wohlgefühl - Nehmen Sie sich Zeit für sich selbst",
        )

    def test_no_matches(self):
        """Test behavior when filters match no events"""
        # Filter that matches nothing
        filtered = self.collection.include_categories(["NonExistentCategory"])
        self.assertEqual(len(filtered.to_list()), 0)

        # Pattern that matches nothing (neither string nor regex)
        filtered = self.collection.include_titles(["XYZ123"])
        self.assertEqual(len(filtered.to_list()), 0)

    def test_include_categories_exact_match(self):
        """Test that category filtering uses exact match, not substring"""
        # Create events with specific categories
        event_markt = mock_data.get_event(title="Markt Event", categories=["Markt"])
        event_weihnachtsmarkt = mock_data.get_event(
            title="Weihnachtsmarkt Event", categories=["Weihnachtsmarkt"]
        )
        event_both = mock_data.get_event(
            title="Both", categories=["Markt", "Weihnachtsmarkt"]
        )

        collection = EventCollection([event_markt, event_weihnachtsmarkt, event_both])

        # Filter for "Markt" should only match events with exactly "Markt"
        filtered = collection.include_categories(["Markt"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 2)  # event_markt and event_both
        titles = [e.title for e in filtered_events]
        self.assertIn("Markt Event", titles)
        self.assertIn("Both", titles)
        self.assertNotIn("Weihnachtsmarkt Event", titles)

    def test_exclude_categories_exact_match(self):
        """Test that category exclusion uses exact match, not substring"""
        # Create events with specific categories
        event_markt = mock_data.get_event(title="Markt Event", categories=["Markt"])
        event_weihnachtsmarkt = mock_data.get_event(
            title="Weihnachtsmarkt Event", categories=["Weihnachtsmarkt"]
        )
        event_both = mock_data.get_event(
            title="Both", categories=["Markt", "Weihnachtsmarkt"]
        )

        collection = EventCollection([event_markt, event_weihnachtsmarkt, event_both])

        # Exclude "Markt" should only exclude events with exactly "Markt"
        filtered = collection.exclude_categories(["Markt"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 1)  # Only Weihnachtsmarkt Event
        self.assertEqual(filtered_events[0].title, "Weihnachtsmarkt Event")

    def test_exclude_locations_string(self):
        """Test location exclusion with string matching"""
        # Create events with specific locations
        event_online = mock_data.get_event(title="Online Event", location="online")
        event_concert_hall = mock_data.get_event(
            title="Concert Hall Event", location="Concert Hall"
        )
        event_remote = mock_data.get_event(title="Remote Event", location="remote")

        collection = EventCollection([event_online, event_concert_hall, event_remote])

        # Exclude "online" should filter out events with "online" in location
        filtered = collection.exclude_locations(["online"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 2)
        titles = [e.title for e in filtered_events]
        self.assertIn("Concert Hall Event", titles)
        self.assertIn("Remote Event", titles)
        self.assertNotIn("Online Event", titles)

    def test_exclude_locations_regex(self):
        """Test location exclusion with regex patterns"""
        # Create events with different locations
        event_online = mock_data.get_event(title="Online Event", location="online")
        event_web = mock_data.get_event(title="Web Event", location="world wide web")
        event_venue = mock_data.get_event(title="Venue Event", location="Paris Hall")
        event_no_location = mock_data.get_event(title="No Location", location=None)

        collection = EventCollection(
            [event_online, event_web, event_venue, event_no_location]
        )

        # Exclude locations matching "world.*web" pattern
        filtered = collection.exclude_locations(["world.*web"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 3)
        titles = [e.title for e in filtered_events]
        self.assertIn("Online Event", titles)
        self.assertIn("Venue Event", titles)
        self.assertIn("No Location", titles)
        self.assertNotIn("Web Event", titles)

    def test_exclude_locations_case_insensitive(self):
        """Test that location exclusion is case-insensitive"""
        event1 = mock_data.get_event(title="Event 1", location="ONLINE")
        event2 = mock_data.get_event(title="Event 2", location="Online")
        event3 = mock_data.get_event(title="Event 3", location="online")
        event4 = mock_data.get_event(title="Event 4", location="Paris")

        collection = EventCollection([event1, event2, event3, event4])

        # All case variations of "online" should be excluded
        filtered = collection.exclude_locations(["online"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 1)
        self.assertEqual(filtered_events[0].title, "Event 4")

    def test_exclude_locations_preserves_no_location_events(self):
        """Test that events with no location are preserved"""
        event_online = mock_data.get_event(title="Online", location="online")
        event_no_location1 = mock_data.get_event(title="No Location 1", location=None)
        event_no_location2 = mock_data.get_event(title="No Location 2", location="")
        event_venue = mock_data.get_event(title="Venue", location="Paris Hall")

        collection = EventCollection(
            [event_online, event_no_location1, event_no_location2, event_venue]
        )

        # Exclude "online"
        filtered = collection.exclude_locations(["online"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 3)
        titles = [e.title for e in filtered_events]
        self.assertIn("No Location 1", titles)
        self.assertIn("No Location 2", titles)
        self.assertIn("Venue", titles)

    def test_exclude_locations_multiple_patterns(self):
        """Test location exclusion with multiple patterns"""
        event_online = mock_data.get_event(title="Online", location="online")
        event_remote = mock_data.get_event(title="Remote", location="remote")
        event_studio = mock_data.get_event(title="Studio", location="recording studio")
        event_venue = mock_data.get_event(title="Venue", location="Paris Hall")

        collection = EventCollection(
            [event_online, event_remote, event_studio, event_venue]
        )

        # Exclude multiple patterns
        filtered = collection.exclude_locations(["online", "remote", "studio"])
        filtered_events = filtered.to_list()

        self.assertEqual(len(filtered_events), 1)
        self.assertEqual(filtered_events[0].title, "Venue")
