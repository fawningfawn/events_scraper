"""Integration tests for plugin loader"""

import unittest

from plugins import load_many


class TestPluginLoader(unittest.TestCase):
    """Test plugin loading mechanism"""

    def test_load_notifiers_returns_modules(self):
        """Test that load_many returns notifier modules"""
        notifiers = list(load_many("plugins.notifiers"))

        # Should load at least the signal notifier
        self.assertGreater(len(notifiers), 0)

    def test_signal_notifier_loads_successfully(self):
        """Test that signal notifier module loads without errors"""
        notifiers = list(load_many("plugins.notifiers"))

        # Find signal notifier
        signal_notifier = None
        for notifier in notifiers:
            if hasattr(notifier, "name") and notifier.name == "signal":
                signal_notifier = notifier
                break

        self.assertIsNotNone(
            signal_notifier, "Signal notifier not found in loaded plugins"
        )

    def test_signal_notifier_has_send_method(self):
        """Test that loaded signal notifier has send method"""
        notifiers = list(load_many("plugins.notifiers"))

        for notifier in notifiers:
            if hasattr(notifier, "name") and notifier.name == "signal":
                self.assertTrue(
                    hasattr(notifier, "send"),
                    "Signal notifier missing send method",
                )
                self.assertTrue(
                    callable(notifier.send),
                    "Signal notifier send is not callable",
                )
                break

    def test_notifier_dict_creation(self):
        """Test that notifiers can be loaded into a dict like the notification system does"""
        # This is exactly how notifications.py uses load_many
        notifiers = {n.name: n for n in load_many("plugins.notifiers")}

        # Should have signal notifier
        self.assertIn("signal", notifiers)
        self.assertTrue(hasattr(notifiers["signal"], "send"))

    def test_no_underscore_modules_loaded(self):
        """Test that modules starting with underscore are skipped"""
        notifiers = list(load_many("plugins.notifiers"))

        # Check that no private modules are loaded
        for notifier in notifiers:
            module_name = notifier.__class__.__module__
            # Module name should not reference _notifier_base
            self.assertNotIn("_notifier_base", module_name)
