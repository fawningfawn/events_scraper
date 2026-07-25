"""Smoke tests for `dump_events` command.

Each test instantiates the command, builds a minimal argparse Namespace
matching the subparser, and verifies the command returns cleanly and
produces a non-empty result.

These do not hit the network and use the in-memory test database.
"""

import io
from contextlib import redirect_stdout

from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from plugins.commands.dump_events import DumpEventsCommand
from tests.lib.core.test_base import BaseTestCase


class _Args:
    """Minimal stand-in for argparse Namespace."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestDumpEvents(BaseTestCase):

    def setUp(self):
        super().setUp()
        init_database("sqlite:///:memory:")
        session = get_session()
        from events_scraper.lib import mock_data

        self._title_a = "Linux Meetup"
        self._title_b = "Python Workshop"
        self._title_c = "Rust Conference"
        self._group = "paris"

        mock_data.get_orm_event(
            session=session,
            title=self._title_a,
            scraper=f"{self._group}.meetup",
            date="2026-03-15",
        )
        mock_data.get_orm_event(
            session=session,
            title=self._title_b,
            scraper=f"{self._group}.workshop",
            date="2026-04-20",
        )
        mock_data.get_orm_event(
            session=session,
            title=self._title_c,
            scraper="munich.conf",
            date="2026-05-01",
        )
        session.commit()
        session.close()

    def _run(self, **kwargs) -> tuple:
        defaults = dict(
            title=None,
            group=None,
            scraper=[],
            date=None,
            date_from=None,
            date_to=None,
            limit=200,
            json=False,
        )
        defaults.update(kwargs)
        args = _Args(**defaults)
        cmd = DumpEventsCommand()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd.run(args)
        return rc, buf.getvalue()

    def test_dump_all(self):
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertIn(self._title_a, out)
        self.assertIn(self._title_b, out)
        self.assertIn(self._title_c, out)
        self.assertIn("Total: 3", out)

    def test_dump_by_group(self):
        rc, out = self._run(group=self._group)
        self.assertEqual(rc, 0)
        self.assertIn(self._title_a, out)
        self.assertIn(self._title_b, out)
        self.assertNotIn(self._title_c, out)
        self.assertIn("Total: 2", out)

    def test_dump_by_scraper(self):
        rc, out = self._run(scraper=["munich.conf"])
        self.assertEqual(rc, 0)
        self.assertIn(self._title_c, out)
        self.assertNotIn(self._title_a, out)
        self.assertIn("Total: 1", out)

    def test_dump_by_date_from(self):
        rc, out = self._run(date_from="2026-04-01")
        self.assertEqual(rc, 0)
        self.assertNotIn(self._title_a, out)
        self.assertIn(self._title_b, out)
        self.assertIn(self._title_c, out)

    def test_dump_by_title_regex(self):
        rc, out = self._run(title=r"Python|Linux")
        self.assertEqual(rc, 0)
        self.assertIn(self._title_a, out)
        self.assertIn(self._title_b, out)
        self.assertNotIn(self._title_c, out)

    def test_dump_json(self):
        rc, out = self._run(json=True)
        self.assertEqual(rc, 0)
        import json

        payload = json.loads(out)
        self.assertEqual(len(payload), 3)
        self.assertEqual(
            {e["title"] for e in payload}, {self._title_a, self._title_b, self._title_c}
        )

    def test_dump_limit(self):
        rc, out = self._run(limit=1)
        self.assertEqual(rc, 0)
        self.assertIn("Total: 1", out)

    def test_dump_invalid_date_returns_error(self):
        rc, out = self._run(date="not-a-date")
        self.assertEqual(rc, 2)
        self.assertIn("Error:", out)

    def test_dump_date_and_range_conflict_returns_error(self):
        rc, out = self._run(date="2026-03-15", date_from="2026-04-01")
        self.assertEqual(rc, 2)
        self.assertIn("Error:", out)


class TestDumpEventsRegression(BaseTestCase):
    """Regression: `dump_events` was using `city=` kwarg that does not exist.

    See: TypeError ... unexpected keyword argument 'city'
    """

    def setUp(self):
        super().setUp()
        init_database("sqlite:///:memory:")
        session = get_session()
        from events_scraper.lib import mock_data

        mock_data.get_orm_event(
            session=session,
            title="Sample",
            scraper="paris.test",
            date="2026-03-15",
        )
        session.commit()
        session.close()

    def test_dump_with_date_from_runs_end_to_end(self):
        """`--date-from` (no exact `--date`) used to crash with TypeError.

        Run the command end-to-end against an in-memory database so any
        regression in the keyword names surfaces here.
        """
        args = _Args(
            title=None,
            group=None,
            scraper=[],
            date=None,
            date_from="2026-01-01",
            date_to="2026-12-31",
            limit=200,
            json=False,
        )
        cmd = DumpEventsCommand()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd.run(args)
        self.assertEqual(rc, 0)
        self.assertIn("Sample", buf.getvalue())
