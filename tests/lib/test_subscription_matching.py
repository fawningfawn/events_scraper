"""Test subscription matching logic"""

import unittest

from events_scraper.lib.subscriptions.matching import matches_subscription


class TestSubscriptionMatching(unittest.TestCase):
    """Test subscription matching logic"""

    def test_matches_subscription_case_insensitive_substring(self):
        """Test matches_subscription returns True for case-insensitive substring match"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type(
            "Event", (), {"title": "Paris Philharmonic Kammerorchester in Concert"}
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_lowercase_keyword(self):
        """Test matches with lowercase keyword"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "kammerorchester", "body_keyword": None},
        )()
        event = type(
            "Event", (), {"title": "Paris Philharmonic KAMMERORCHESTER in Concert"}
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_keyword_not_found(self):
        """Test returns False when keyword not in event title"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type("Event", (), {"title": "Paris Philharmonic Symphony Orchestra"})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_empty_keyword(self):
        """Test returns False for empty keyword"""
        subscription = type(
            "Subscription", (), {"title_keyword": None, "body_keyword": None}
        )()
        event = type("Event", (), {"title": "Some Event"})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_special_characters(self):
        """Test handles special characters in keyword"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Philharmonie (NY)", "body_keyword": None},
        )()
        event = type("Event", (), {"title": "New York Philharmonie (NY) Concert"})()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_with_none_event(self):
        """Test handles None event gracefully"""
        subscription = type(
            "Subscription", (), {"title_keyword": "test", "body_keyword": None}
        )()
        event = None

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_with_none_subscription(self):
        """Test handles None subscription gracefully"""
        subscription = None
        event = type("Event", (), {"title": "Some Event"})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_with_none_title(self):
        """Test handles event with None title"""
        subscription = type(
            "Subscription", (), {"title_keyword": "test", "body_keyword": None}
        )()
        event = type("Event", (), {"title": None})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_very_long_keyword(self):
        """Test handles very long keywords"""
        long_keyword = "A" * 1000
        subscription = type(
            "Subscription", (), {"title_keyword": long_keyword, "body_keyword": None}
        )()
        event = type("Event", (), {"title": long_keyword + " Concert"})()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_whitespace_keyword(self):
        """Test handles whitespace-only keyword"""
        subscription = type(
            "Subscription", (), {"title_keyword": "   ", "body_keyword": None}
        )()
        event = type("Event", (), {"title": "Some Event"})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_substring_not_word_boundary(self):
        """Test substring matching (not word boundary sensitive)"""
        subscription = type(
            "Subscription", (), {"title_keyword": "phil", "body_keyword": None}
        )()
        event = type("Event", (), {"title": "Philharmonie Concert"})()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_matches_in_body(self):
        """Test matches subscription keyword found in event body"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": None, "body_keyword": "Kammerorchester"},
        )()
        event = type(
            "Event",
            (),
            {
                "title": "Classical Concert",
                "body": "Paris Philharmonic Kammerorchester performs tonight",
            },
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_matches_in_title_or_body(self):
        """Test matches if keyword in title OR body (but OR is not tested here with AND logic)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type(
            "Event",
            (),
            {
                "title": "Paris Philharmonic Kammerorchester Concert",
                "body": "A different event description",
            },
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_with_empty_body(self):
        """Test works when body is None/empty (matches title instead)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type(
            "Event",
            (),
            {"title": "Paris Philharmonic Kammerorchester Concert", "body": None},
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_with_empty_title(self):
        """Test works when title is empty (matches body instead)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": None, "body_keyword": "Kammerorchester"},
        )()
        event = type(
            "Event",
            (),
            {"title": "", "body": "Paris Philharmonic Kammerorchester performance"},
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_with_both_empty(self):
        """Test returns False when both title and body are None/empty"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type("Event", (), {"title": "", "body": None})()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_special_characters_in_body(self):
        """Test handles special characters in body"""
        subscription = type(
            "Subscription", (), {"title_keyword": None, "body_keyword": "Test (Event)"}
        )()
        event = type(
            "Event",
            (),
            {"title": "Concert", "body": "This is a Test (Event) description"},
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_whitespace_only_body(self):
        """Test handles whitespace-only body (treated as empty)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": None},
        )()
        event = type(
            "Event",
            (),
            {"title": "Paris Philharmonic Kammerorchester Concert", "body": "   "},
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)  # Should match title since body is whitespace-only

    def test_matches_subscription_with_both_keywords_and_logic(self):
        """Test with both title and body keywords uses AND logic"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": "solo"},
        )()
        event = type(
            "Event",
            (),
            {
                "title": "Paris Philharmonic Kammerorchester Concert",
                "body": "Members perform solo pieces",
            },
        )()

        result = matches_subscription(event, subscription)
        self.assertTrue(result)

    def test_matches_subscription_with_both_keywords_missing_title(self):
        """Test with both keywords fails if title keyword missing (AND logic)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": "solo"},
        )()
        event = type(
            "Event",
            (),
            {"title": "Concert", "body": "Members perform solo pieces"},
        )()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)

    def test_matches_subscription_with_both_keywords_missing_body(self):
        """Test with both keywords fails if body keyword missing (AND logic)"""
        subscription = type(
            "Subscription",
            (),
            {"title_keyword": "Kammerorchester", "body_keyword": "solo"},
        )()
        event = type(
            "Event",
            (),
            {
                "title": "Paris Philharmonic Kammerorchester Concert",
                "body": "A classical concert",
            },
        )()

        result = matches_subscription(event, subscription)
        self.assertFalse(result)
