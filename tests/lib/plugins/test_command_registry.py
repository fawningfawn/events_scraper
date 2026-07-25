"""Tests for command plugin registry/autodiscovery."""

import contextlib
import io
import types
import unittest
from unittest.mock import patch

from plugins.command_base import CommandPlugin
from plugins.command_registry import discover_command_plugins
from plugins.command_registry import DuplicateCommandNameError
from plugins.command_registry import run_command


class _DummyCommand(CommandPlugin):
    def register_subparser(self, subparsers):
        return subparsers.add_parser(self.name)

    def run(self, args):
        return 0


class TestCommandRegistry(unittest.TestCase):
    def test_discover_command_plugins_sorted_deterministic(self):
        mod_b = types.SimpleNamespace(
            __name__="plugins.commands.b",
            plugins=[_DummyCommand()],
        )
        mod_a = types.SimpleNamespace(
            __name__="plugins.commands.a",
            plugins=[_DummyCommand()],
        )

        with (
            patch("plugins.command_registry.load_from_dir", return_value=[]),
            patch("plugins.command_registry.load_many", return_value=[mod_b, mod_a]),
        ):
            plugins = discover_command_plugins()

        self.assertEqual([p.name for p in plugins], ["a", "b"])

    def test_discover_command_plugins_requires_single_plugin_per_module(self):
        mod = types.SimpleNamespace(
            __name__="plugins.commands.multi",
            plugins=[_DummyCommand(), _DummyCommand()],
        )
        with (
            patch("plugins.command_registry.load_from_dir", return_value=[]),
            patch("plugins.command_registry.load_many", return_value=[mod]),
        ):
            with self.assertRaises(ValueError):
                discover_command_plugins()

    def test_discover_command_plugins_duplicate_name_raises(self):
        mod1 = types.SimpleNamespace(
            __name__="plugins.commands.dup",
            plugins=[_DummyCommand()],
        )
        mod2 = types.SimpleNamespace(
            __name__="plugins.commands.dup",
            plugins=[_DummyCommand()],
        )

        with (
            patch("plugins.command_registry.load_from_dir", return_value=[]),
            patch("plugins.command_registry.load_many", return_value=[mod1, mod2]),
        ):
            with self.assertRaises(DuplicateCommandNameError):
                discover_command_plugins()

    def test_root_help_lists_only_flags_and_commands(self):
        mod_a = types.SimpleNamespace(
            __name__="plugins.commands.a",
            plugins=[_DummyCommand()],
        )
        mod_b = types.SimpleNamespace(
            __name__="plugins.commands.b",
            plugins=[_DummyCommand()],
        )

        with patch("plugins.command_registry.load_many", return_value=[mod_a, mod_b]):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = run_command(["--help"])

        output = stdout.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("root flags:", output)
        self.assertIn("commands:", output)
        self.assertIn("  a", output)
        self.assertIn("  b", output)
        self.assertNotIn("positional arguments:", output)
        self.assertNotIn("Events management commands", output)

    def test_no_args_prints_root_help(self):
        mod = types.SimpleNamespace(
            __name__="plugins.commands.cmd",
            plugins=[_DummyCommand()],
        )

        with patch("plugins.command_registry.load_many", return_value=[mod]):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = run_command([])

        output = stdout.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("commands:", output)
        self.assertIn("  cmd", output)

    def test_help_command_prints_subcommand_help(self):
        mod = types.SimpleNamespace(
            __name__="plugins.commands.cmd",
            plugins=[_DummyCommand()],
        )

        with patch("plugins.command_registry.load_one", return_value=mod):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = run_command(["help", "cmd"])

        output = stdout.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("usage:", output)

    def test_specific_command_does_not_scan_all_modules(self):
        mod = types.SimpleNamespace(
            __name__="plugins.commands.cmd",
            plugins=[_DummyCommand()],
        )
        with patch("plugins.command_registry.load_one", return_value=mod):
            with patch("plugins.command_registry.load_many") as mock_load_many:
                rc = run_command(["cmd"])

        self.assertEqual(rc, 0)
        mock_load_many.assert_not_called()
