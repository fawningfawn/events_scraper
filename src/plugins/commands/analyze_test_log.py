"""Analyze test log files and extract failures."""

from __future__ import annotations

import glob
import os
import re
from argparse import Namespace

from plugins.command_base import CommandPlugin


def find_latest_log():
    """Find the most recent test output log."""
    log_pattern = "reports/test_output_*.log"
    log_files = glob.glob(log_pattern)

    if not log_files:
        print(f"No log files found matching {log_pattern}")
        return None

    return max(log_files, key=os.path.getmtime)


def analyze_log(log_file):
    """Parse test log and extract failure information."""
    with open(log_file, "r") as f:
        content = f.read()

    pattern = r"((?:FAIL|ERROR)\s+\[[\d.]+s\]:.*?)(?=(?:FAIL|ERROR)\s+\[|={70}|Ran \d+ tests|$)"
    failures = re.findall(pattern, content, re.DOTALL)

    if not failures:
        print("No test failures found!")
        return 0

    print(f"Found {len(failures)} test failure(s):\n")

    for i, failure in enumerate(failures, 1):
        print("=" * 70)
        print(f"FAILURE {i}:")
        print("=" * 70)
        print(failure[:3000])
        print()

    return len(failures)


class AnalyzeTestLogCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Analyze the latest or given test log",
            description=__doc__,
        )
        parser.add_argument("log_file", nargs="?")
        return parser

    def run(self, args: Namespace) -> int:
        log_file = args.log_file or find_latest_log()
        if not log_file:
            return 1
        print(f"Analyzing log: {log_file}\n")
        return analyze_log(log_file)


plugins = [AnalyzeTestLogCommand()]
