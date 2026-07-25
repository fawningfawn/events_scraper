"""Tests for script-backed command modules."""

import sys
import unittest
from datetime import date
from importlib import import_module
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from plugins.command_registry import build_command_parser
from plugins.command_registry import load_command_plugin


class TestScriptsCommandPlugins(unittest.TestCase):
    def test_script_commands_are_exposed(self):
        plugin = load_command_plugin("analyze_test_log")
        _, commands, _ = build_command_parser(plugins=[plugin])
        self.assertIn("analyze_test_log", commands)

    def test_script_command_help_uses_module_docstring(self):
        plugin = load_command_plugin("analyze_test_log")
        _, _, subparsers = build_command_parser(plugins=[plugin])
        parser = subparsers["analyze_test_log"]
        self.assertIn("Analyze test log files", parser.format_help())

    def test_info_command_is_exposed(self):
        plugin = load_command_plugin("info")
        _, commands, _ = build_command_parser(plugins=[plugin])
        self.assertIn("info", commands)

    def test_scrape_command_uses_loader_not_eventscli(self):
        plugin = load_command_plugin("scrape")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["scrape", "paris.garage_sb"])
        command_module = import_module("plugins.commands.scrape")

        with (
            patch.object(
                command_module, "parse_date_argument", return_value=date(2026, 3, 22)
            ),
            patch.object(
                command_module, "_execute_scraping", return_value=[]
            ) as mock_execute,
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_execute.assert_called_once()
        self.assertEqual(mock_execute.call_args.args[0], ["paris.garage_sb"])

    def test_scrape_command_defaults_logging_to_stdout_stream(self):
        plugin = load_command_plugin("scrape")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["scrape"])
        command_module = import_module("plugins.commands.scrape")

        with (
            patch.object(
                command_module, "parse_date_argument", return_value=date(2026, 3, 22)
            ),
            patch.object(command_module, "_execute_scraping", return_value=[]),
            patch.object(command_module, "setup_logging") as mock_setup_logging,
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        self.assertIs(mock_setup_logging.call_args.kwargs["log_stream"], sys.stdout)
        self.assertIsNone(mock_setup_logging.call_args.kwargs["log_file"])

    def test_scrape_command_passes_scrape_details_flag(self):
        plugin = load_command_plugin("scrape")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["scrape", "--scrape-details"])
        command_module = import_module("plugins.commands.scrape")

        with (
            patch.object(
                command_module, "parse_date_argument", return_value=date(2026, 3, 22)
            ),
            patch.object(
                command_module, "_execute_scraping", return_value=[]
            ) as mock_execute,
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(mock_execute.call_args.kwargs["fetch_details"])

    def test_info_command_prints_runtime_report(self):
        plugin = load_command_plugin("info")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["info"])
        command_module = import_module("plugins.commands.info")

        fake_config = object()
        with (
            patch.object(command_module, "load_config", return_value=fake_config),
            patch.object(command_module, "configure_database") as mock_configure,
            patch.object(
                command_module, "collect_runtime_info", return_value=object()
            ) as mock_collect,
            patch.object(
                command_module, "format_runtime_info", return_value="REPORT"
            ) as mock_format,
            patch("builtins.print") as mock_print,
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_configure.assert_called_once_with(database_url=None, config=fake_config)
        mock_collect.assert_called_once_with()
        mock_format.assert_called_once()
        mock_print.assert_called_once_with("REPORT")

    def test_command_plugins_have_no_eventscli_runtime_dependency(self):
        commands_dir = Path("src/plugins/commands")
        python_files = sorted(commands_dir.glob("*.py"))

        for command_file in python_files:
            if command_file.name == "__init__.py":
                continue
            content = command_file.read_text(encoding="utf-8")
            self.assertNotIn("eventscli", content, str(command_file))

    def test_dump_url_command_renders_full_url_path(self):
        plugin = load_command_plugin("dump_url")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(
            ["dump_url", "http://example.com:1234/status/scraper/eventfoo?errors=on"]
        )
        command_module = import_module("plugins.commands.dump_url")

        fake_response = MagicMock()
        fake_response.get_data.return_value = "<html>ok</html>"
        fake_response.status_code = 200
        fake_response.status = "200 OK"
        fake_response.headers.items.return_value = [("Content-Type", "text/html")]

        fake_client_ctx = MagicMock()
        fake_client_ctx.__enter__.return_value = fake_client_ctx
        fake_client_ctx.__exit__.return_value = None
        fake_client_ctx.open.return_value = fake_response

        fake_app = MagicMock()
        fake_app.test_client.return_value = fake_client_ctx

        with (
            patch.object(command_module, "load_config"),
            patch.object(command_module, "configure_database"),
            patch.object(command_module, "create_app", return_value=fake_app),
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        fake_client_ctx.open.assert_called_once_with(
            path="/status/scraper/eventfoo?errors=on",
            method="GET",
        )

    def test_delete_events_command_uses_scraper_scope(self):
        plugin = load_command_plugin("delete_events")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["delete_events", "--scraper", "paris.kube_kultur"])
        command_module = import_module("plugins.commands.delete_events")

        with (
            patch.object(
                command_module, "_scraper_exists_or_has_data", return_value=True
            ),
            patch.object(command_module, "delete_events_by_scraper") as mock_delete,
        ):
            mock_delete.return_value = {
                "events": 3,
                "notifications": 1,
                "event_details": 2,
                "scraper_status": 1,
            }
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_delete.assert_called_once_with("paris.kube_kultur")

    def test_delete_events_command_defaults_to_conference_scope(self):
        plugin = load_command_plugin("delete_events")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["delete_events", "--group", "testgroup"])
        command_module = import_module("plugins.commands.delete_events")

        with patch.object(
            command_module, "delete_group_events", return_value=7
        ) as mock_delete:
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_delete.assert_called_once_with("testgroup")

    def test_delete_events_command_conference_flag(self):
        plugin = load_command_plugin("delete_events")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["delete_events", "--group", "festivals"])
        command_module = import_module("plugins.commands.delete_events")

        with patch.object(
            command_module, "delete_group_events", return_value=4
        ) as mock_delete:
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 0)
        mock_delete.assert_called_once_with("festivals")

    def test_delete_events_command_unknown_scraper_errors(self):
        plugin = load_command_plugin("delete_events")
        parser, _, _ = build_command_parser(plugins=[plugin])
        args = parser.parse_args(["delete_events", "--scraper", "xoxo"])
        command_module = import_module("plugins.commands.delete_events")

        with (
            patch.object(
                command_module, "_scraper_exists_or_has_data", return_value=False
            ),
            patch.object(command_module, "delete_events_by_scraper") as mock_delete,
        ):
            exit_code = plugin.run(args)

        self.assertEqual(exit_code, 1)
        mock_delete.assert_not_called()
