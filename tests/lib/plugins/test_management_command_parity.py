"""Parity tests for retained management command behavior."""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from plugins.command_registry import build_command_parser
from plugins.command_registry import load_command_plugin


class TestManagementCommandParity(unittest.TestCase):
    """End-to-end command runtime parity checks."""

    def test_events_notify_flag_runs_notify_path(self):
        plugin = load_command_plugin("events")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["events", "--notify"])

        mock_notify = Mock(return_value=0)
        with patch.dict(plugin.run.__globals__, {"_run_notify": mock_notify}):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_notify.assert_called_once_with()
