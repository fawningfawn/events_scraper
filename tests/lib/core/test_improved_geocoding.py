#!/usr/bin/env python3
"""
Test the improved geocoding functionality with previously failed locations
"""

import shutil
import unittest
from unittest.mock import patch

from events_scraper.lib.core import Geocoder


@patch("events_scraper.lib.core.Nominatim")
class TestImprovedGeocoding(unittest.TestCase):
    """Test improved geocoding functionality"""

    def setUp(self):
        self.geocoder = Geocoder("Paris, France")

    def tearDown(self):
        try:

            shutil.rmtree("./test_todo")
        except FileNotFoundError:
            pass

    def test_location_cleaning_generates_variations(self, mock_nominatim):
        """Test that location cleaning generates expected variations"""
        test_cases = [
            "Maison des Artistes Parisiens S.A.R.L.",
            "Théâtre de la Ville (Salle Sarah Bernhardt)",
            "Quai de Seine / Musée d'Orsay",
            "Assoc. Centre Culturel de Mont-Saint-Michel",
            "Centre Culturel et Médiathèque de Montmartre",
        ]

        for location in test_cases:
            with self.subTest(location=location):
                variations = self.geocoder._clean_location_string(location)
                # Should always include the original
                self.assertIn(location, variations)
                # Should have at least one variation
                self.assertGreaterEqual(len(variations), 1)

    def test_specific_location_cleaning_patterns(self, mock_nominatim):
        """Test specific location cleaning patterns"""
        test_cases = {
            "Galerie d'Art Paris AG": [
                "Galerie d'Art Paris AG",
                "Galerie d'Art Paris",
            ],
            "Théâtre du Châtelet (Salle des Fêtes)": [
                "Théâtre du Châtelet (Salle des Fêtes)",
                "Théâtre du Châtelet",
            ],
            "Quai de Seine / Musée d'Orsay": [
                "Quai de Seine / Musée d'Orsay",
                "Quai de Seine",
                "Musée d'Orsay",
            ],
            "Assoc. Centre Culturel de Mont-Saint-Michel": [
                "Assoc. Centre Culturel de Mont-Saint-Michel",
                "Mont-Saint-Michel",
            ],
        }

        for original, expected_contains in test_cases.items():
            with self.subTest(location=original):
                variations = self.geocoder._clean_location_string(original)

                # Check that expected components are present
                for expected in expected_contains:
                    self.assertIn(
                        expected,
                        variations,
                        f"Expected '{expected}' in variations for '{original}'",
                    )
