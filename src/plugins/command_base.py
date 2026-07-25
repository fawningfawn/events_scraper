"""Command plugin base contracts."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from argparse import ArgumentParser
from argparse import Namespace


class CommandPlugin(ABC):
    """Base contract for management command plugins."""

    @property
    def name(self) -> str:
        """Command name derived from module filename by default."""
        command_name = getattr(self, "_command_name", None)
        if command_name:
            return command_name
        return self.__class__.__module__.rsplit(".", 1)[-1]

    @abstractmethod
    def register_subparser(self, subparsers) -> ArgumentParser:
        """Register this command in the given subparsers collection."""

    @abstractmethod
    def run(self, args: Namespace) -> int:
        """Execute command and return process exit code."""
