"""Autodiscovery and runtime registry for command plugins."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict
from typing import Iterable
from typing import List

from plugins import load_from_dir
from plugins import load_many
from plugins import load_one
from plugins.command_base import CommandPlugin


class DuplicateCommandNameError(ValueError):
    """Raised when two command plugins register the same command name."""


def _package_command_dirs():
    packages_dir = Path(__file__).resolve().parent.parent / "packages"
    if packages_dir.is_dir():
        for item in sorted(os.listdir(packages_dir)):
            cmd_dir = packages_dir / item / "commands"
            if cmd_dir.is_dir():
                yield str(cmd_dir)


def _iter_plugin_objects(module) -> Iterable[CommandPlugin]:
    plugins = getattr(module, "plugins", None)
    if plugins is not None:
        for item in plugins:
            yield item


def _module_command_name(module_name: str) -> str:
    return module_name.rsplit(".", 1)[-1]


def discover_command_plugins(path: str = "plugins.commands") -> List[CommandPlugin]:
    """Discover command plugins from a namespace in deterministic order."""
    discovered: Dict[str, CommandPlugin] = {}

    modules = sorted(load_many(path), key=lambda m: getattr(m, "__name__", ""))
    for cmd_dir in _package_command_dirs():
        modules.extend(load_from_dir(cmd_dir))

    for module in modules:
        items = list(_iter_plugin_objects(module))
        if len(items) != 1:
            raise ValueError(
                f"Command module '{module.__name__}' must export exactly one plugin"
            )

        plugin = items[0]
        if not isinstance(plugin, CommandPlugin):
            raise TypeError(
                f"Invalid command plugin in {module.__name__}: {type(plugin)!r}"
            )

        command_name = _module_command_name(module.__name__)
        if command_name in discovered:
            raise DuplicateCommandNameError(
                f"Duplicate command plugin name: {command_name}"
            )
        setattr(plugin, "_command_name", command_name)
        discovered[command_name] = plugin

    return [discovered[name] for name in sorted(discovered)]


def load_command_plugin(
    command_name: str,
    path: str = "plugins.commands",
) -> CommandPlugin | None:
    """Load exactly one command plugin module by command name."""
    module = load_one(f"{path}.{command_name}")
    if module is None:
        for cmd_dir in _package_command_dirs():
            mod_file = os.path.join(cmd_dir, f"{command_name}.py")
            if os.path.isfile(mod_file):
                for m in load_from_dir(cmd_dir):
                    if _module_command_name(m.__name__) == command_name:
                        module = m
                        break
                if module is not None:
                    break
    if module is None:
        return None

    items = list(_iter_plugin_objects(module))
    if len(items) != 1:
        raise ValueError(
            f"Command module '{path}.{command_name}' must export exactly one plugin"
        )

    plugin = items[0]
    if not isinstance(plugin, CommandPlugin):
        raise TypeError(
            f"Invalid command plugin in {path}.{command_name}: {type(plugin)!r}"
        )
    setattr(plugin, "_command_name", command_name)

    return plugin


def build_command_parser(
    plugins: List[CommandPlugin] | None = None,
    description: str = "Events management commands",
) -> tuple[
    argparse.ArgumentParser,
    Dict[str, CommandPlugin],
    Dict[str, argparse.ArgumentParser],
]:
    """Build argparse parser from discovered command plugins."""
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="command")

    if plugins is None:
        plugins = discover_command_plugins()
    mapping: Dict[str, CommandPlugin] = {}
    subparser_map: Dict[str, argparse.ArgumentParser] = {}

    for plugin in plugins:
        subparser = plugin.register_subparser(subparsers)
        if subparser is None:
            raise ValueError(f"Command plugin {plugin.name} did not return a subparser")
        mapping[plugin.name] = plugin
        subparser_map[plugin.name] = subparser

    return parser, mapping, subparser_map


def _root_flags(parser: argparse.ArgumentParser) -> list[str]:
    """Collect root-level optional flags from the parser."""
    flags: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            continue
        if not action.option_strings:
            continue
        flags.extend(action.option_strings)
    return sorted(set(flags))


def _format_root_help(
    parser: argparse.ArgumentParser,
    commands: Dict[str, CommandPlugin],
    prog: str = "manage.py",
) -> str:
    """Render concise top-level help: root flags + command names."""
    lines = [
        f"usage: {prog} [ROOT_FLAGS] <command> [args]",
        "",
    ]

    flags = _root_flags(parser)
    lines.append("root flags:")
    if flags:
        for flag in flags:
            lines.append(f"  {flag}")
    else:
        lines.append("  (none)")

    lines.extend(["", "commands:"])
    for name in sorted(commands):
        lines.append(f"  {name}")
    return "\n".join(lines)


def run_command(argv: list[str] | None = None) -> int:
    """Parse and run command plugin from argv."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in {"-h", "--help"}:
        parser, commands, _ = build_command_parser()
        print(_format_root_help(parser, commands, prog=parser.prog))
        return 0

    if argv[0] == "help":
        if len(argv) == 1:
            parser, commands, _ = build_command_parser()
            print(_format_root_help(parser, commands, prog=parser.prog))
            return 0

        command_name = argv[1]
        plugin = load_command_plugin(command_name)
        if plugin is None:
            print(f"Unknown command: {command_name}", file=sys.stderr)
            return 2

        parser, _, subparsers = build_command_parser(plugins=[plugin])
        command_parser = subparsers[command_name]
        command_parser.print_help()
        return 0

    command_name = argv[0]
    plugin = load_command_plugin(command_name)
    if plugin is None:
        print(f"Unknown command: {command_name}", file=sys.stderr)
        return 2

    parser, commands, _ = build_command_parser(plugins=[plugin])
    args = parser.parse_args(argv)

    return commands[args.command].run(args)
