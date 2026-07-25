"""Mock data generators for tests.

Provides primitive generators (random words, dates, URLs, etc.) and
higher-level helpers for ORM/dataclass Event and EventDetail objects.
"""

import datetime
import os
import random
import string
import time as time_module
from datetime import date as DateType
from datetime import datetime as dt_cls

from events_scraper.lib.core.models import Event
from events_scraper.lib.core.models import EventDetail
from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.packages import GroupMeta
from events_scraper.lib.packages import Package

# ---------------------------------------------------------------------------
# Primitive generators
# ---------------------------------------------------------------------------


def get_word(min_length=3, max_length=12):
    """Generate a random word from lowercase letters."""
    letters = string.ascii_lowercase
    chosen_length = random.randint(min_length, max_length)
    return "".join(random.choice(letters) for _ in range(chosen_length))


def get_sentence(min_words=3, max_words=8, punctuation="."):
    """Generate a random sentence."""
    num_words = random.randint(min_words, max_words)
    words = [get_word().capitalize() if i == 0 else get_word() for i in range(num_words)]
    return " ".join(words) + punctuation


def get_paragraph(min_sentences=3, max_sentences=8):
    """Generate a random paragraph."""
    sentence_count = random.randint(min_sentences, max_sentences)
    sentences = [get_sentence() for _ in range(sentence_count)]
    return " ".join(sentences)


def get_number(start=1, stop=100):
    """Generate a random integer between start and stop."""
    return random.randint(start, stop)


def get_date(min_age=30, max_age=30, future=None):
    """Generate a random date relative to today.

    Args:
        min_age: minimum days from today
        max_age: maximum days from today
        future: if True, generate future date; if False, past date; if None, random
    """
    age_in_days = random.randint(min_age, max_age)
    if future is None:
        future = bool(random.getrandbits(1))
    if future:
        age_in_days = -abs(age_in_days)
    else:
        age_in_days = abs(age_in_days)
    return datetime.date.today() + datetime.timedelta(days=age_in_days)


def get_url(domain="example.com"):
    """Generate a random URL."""
    path_parts = [get_word() for _ in range(random.randint(1, 3))]
    path = "/".join(path_parts)
    return f"https://{domain}/{path}"


def get_list(item_generator, min_items=0, max_items=5):
    """Generate a list of random items using the provided generator function."""
    num_items = random.randint(min_items, max_items)
    return [item_generator() for _ in range(num_items)]


# ---------------------------------------------------------------------------
# Event / EventDetail / ORM helpers
# ---------------------------------------------------------------------------


def get_event_title():
    """Generate a realistic event title."""
    if random.getrandbits(1):
        word1 = get_word().capitalize()
        word2 = get_word().capitalize()
        return f"{word1} {word2}"
    return get_sentence(min_words=2, max_words=4, punctuation="")


def get_venue_name():
    """Generate a realistic venue name."""
    return f"{get_word().capitalize()} {get_word().capitalize()}"


def get_event_time():
    """Generate a random event time string."""
    hour = random.randint(8, 23)
    minute = random.randint(0, 59)
    if random.getrandbits(1):
        seconds = random.randint(0, 59)
        return f"{hour:02d}:{minute:02d}:{seconds:02d}"
    return f"{hour:02d}:{minute:02d}"


def get_event(**kwargs):
    """Generate a realistic Event object using primitives above.

    Args:
        **kwargs: Override any Event field

    Returns:
        Event: Fully populated Event object
    """
    defaults = {
        "id": get_number(),
        "title": get_event_title(),
        "date": get_date(),
        "time": get_event_time() if random.getrandbits(1) else None,
        "location": get_venue_name(),
        "categories": get_list(
            lambda: get_word().capitalize(), min_items=0, max_items=3
        ),
        "detail_url": get_url(get_word() + ".com"),
        "scraper": f"{get_word()}.{get_word(min_length=2, max_length=3)}",
        "latitude": None,
        "longitude": None,
        "end_date": None,
        "cancelled": False,
        "ctime": time_module.time(),
    }
    defaults.update(kwargs)
    return Event(**defaults)


def get_event_list(count=5, **common_kwargs):
    """Generate a list of events with optional common properties."""
    return [get_event(**common_kwargs) for _ in range(count)]


def get_package(name, scraper_names=None, **group_meta_kwargs):
    """Create an in-memory Package with mock scrapers for testing.

    Args:
        name: Package/group name (e.g. "paris")
        scraper_names: List of scraper_name strings (e.g. ["paris.scraper1"])
        **group_meta_kwargs: Override GroupMeta fields (weight, hide_from_status, etc.)

    Returns:
        Package with pre-cached mock scrapers ready for load_scrapers()
    """
    meta_defaults = {
        "group": name,
        "weight": 10,
    }
    meta_defaults.update(group_meta_kwargs)
    group_meta = GroupMeta(**meta_defaults)
    pkg = Package(name=name, path="", meta=group_meta)

    if scraper_names:

        class _MockScraper:
            def __init__(self, sn):
                self.scraper_name = sn
                self.events_url = ""
                self.base_url = ""

        pkg._scrapers = [_MockScraper(sn) for sn in scraper_names]
    else:
        pkg._scrapers = []

    return pkg


def get_event_detail(**kwargs):
    """Generate a realistic EventDetail object.

    Args:
        **kwargs: Override any EventDetail field

    Returns:
        EventDetail: Fully populated EventDetail object
    """
    defaults = {
        "url": get_url(),
        "content": get_paragraph(),
        "scraper": f"{get_word()}.{get_word(min_length=2, max_length=3)}",
    }
    defaults.update(kwargs)
    return EventDetail(**defaults)


def get_orm_event(session=None, **kwargs):
    """Generate a realistic ORM Event object for testing.

    Args:
        session: SQLAlchemy session (optional). If provided, object is saved before returning.
        **kwargs: Override any ORM Event field
    """
    base_event = get_event(**kwargs)
    orm_event = OrmEvent()
    orm_event.title = base_event.title
    orm_event.detail_url = base_event.detail_url
    orm_event.date = (
        dt_cls.strptime(base_event.date, "%Y-%m-%d").date()
        if isinstance(base_event.date, str)
        else base_event.date
    )
    orm_event.time = base_event.time
    orm_event.location = base_event.location
    orm_event.categories = (
        ",".join(base_event.categories) if base_event.categories else None
    )
    orm_event.latitude = base_event.latitude
    orm_event.longitude = base_event.longitude
    orm_event.scraper = base_event.scraper
    if base_event.end_date:
        if isinstance(base_event.end_date, DateType):
            orm_event.end_date = base_event.end_date
        else:
            orm_event.end_date = dt_cls.strptime(base_event.end_date, "%Y-%m-%d").date()
    else:
        orm_event.end_date = None
    orm_event.cancelled = base_event.cancelled

    if session:
        session.add(orm_event)
        session.flush()
    return orm_event


def get_scraper_status(**kwargs):
    """Generate a realistic ScraperStatus object for testing.

    Args:
        **kwargs: Override any ScraperStatus field

    Returns:
        ScraperStatus: ORM ScraperStatus object with realistic data
    """
    defaults = {
        "scraper_name": get_word(),
        "url": get_url(),
        "timestamp": time_module.time(),
        "status_code": 200,
        "error_message": None,
    }
    defaults.update(kwargs)
    return ScraperStatus(**defaults)


def get_orm_user(session=None, **kwargs):
    """Generate a realistic ORM User object for testing.

    Args:
        session: SQLAlchemy session (optional). If provided, object is saved before returning.
        **kwargs: Override any User field (username, phone_number)
    """
    defaults = {
        "username": f"{get_word()}{random.randint(1000, 9999)}",
        "phone_number": None,
    }
    defaults.update(kwargs)
    user = User(**defaults)
    if session:
        session.add(user)
        session.flush()
    return user


def get_orm_notification(session=None, user=None, event=None, **kwargs):
    """Generate a realistic ORM Notification object for testing.

    Args:
        session: SQLAlchemy session (optional). If provided, object is saved before returning.
        user: User ORM object (required if user_id not in kwargs)
        event: Event ORM object (required if event_id not in kwargs)
        **kwargs: Override any Notification field
    """
    if user is None and "user_id" not in kwargs:
        user = get_orm_user(session=session)
    if event is None and "event_id" not in kwargs:
        event = get_orm_event(session=session)

    defaults = {
        "user_id": user.id if user else None,
        "event_id": event.id if event else None,
        "notify_delta": 259200,
        "send_at": None,
        "sent_at": None,
        "status": "pending",
        "plugin": "signal",
    }
    defaults.update(kwargs)
    notification = Notification(**defaults)
    notification.send_at = notification.calculate_send_at(event)
    if session:
        session.add(notification)
        session.flush()
    return notification


def get_test_package(base_dir, name, **kwargs):
    """Create a minimal Python scraper package in a temp dir."""
    defaults = {
        "weight": 10,
        "nav_label": name.capitalize(),
        "display_name": name.capitalize(),
    }
    defaults.update(kwargs)
    pkg_dir = os.path.join(base_dir, name, "scrapers")
    os.makedirs(pkg_dir, exist_ok=True)
    with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
        f.write(
            "import importlib.util, os\n"
            "_s = importlib.util.spec_from_file_location('_testscraper', os.path.join(__path__[0], '_testscraper.py'))\n"
            "_m = importlib.util.module_from_spec(_s)\n"
            "_s.loader.exec_module(_m)\n"
            "TestScraper = _m.TestScraper\n"
            "def get_scrapers():\n"
            "    return [TestScraper]\n"
        )
    with open(os.path.join(pkg_dir, "_testscraper.py"), "w") as f:
        f.write(
            "from events_scraper.lib.core.scraper import BaseEventScraper\n"
            "class TestScraper(BaseEventScraper):\n"
            "    def __init__(self, target_date=None, only_new=False): pass\n"
            "    def get_event_containers(self, s): return []\n"
            "    def extract_event_from_container(self, c, td): return None\n"
            "    def find_next_page_url(self, s, u): return None\n"
            "    def fetch(self):\n"
            "        from events_scraper.lib.core import EventCollection\n"
            "        return EventCollection([])\n"
        )
    with open(os.path.join(pkg_dir, "metadata.py"), "w") as f:
        f.write(
            f'WEIGHT = {defaults["weight"]}\n'
            f'NAV_LABEL = "{defaults["nav_label"]}"\n'
            f'SUPPORTED_CITIES = [{{"name": "{name}", '
            f'"display_name": "{defaults["display_name"]}"}}]\n'
        )
    return GroupMeta(
        group=name,
        display_name=defaults["display_name"],
        nav_label=defaults["nav_label"],
        weight=defaults["weight"],
        source="python",
    )


# ---------------------------------------------------------------------------
# HTTP mock helpers for integration tests
# ---------------------------------------------------------------------------


class MockHttpResponse:
    """Minimal requests.Response stand-in for transport-level testing."""

    def __init__(self, status_code=200, text="ok"):
        import requests as _requests

        self._resp = _requests.Response()
        self._resp.status_code = status_code
        self._resp.encoding = "utf-8"
        self._resp.url = ""
        self._text = text
        self._resp.raw = None

    @property
    def status_code(self):
        return self._resp.status_code

    @property
    def text(self):
        return self._text

    @property
    def content(self):
        return self._text.encode()

    def __getattr__(self, name):
        return getattr(self._resp, name)


class MockTransport:
    """requests.adapters.BaseAdapter stand-in that returns a canned response.

    To use with requests, pass MockTransport() to session.mount().
    Note: requests_cache patches requests.Session in Docker, so use
    MockTransport.send() directly with a PreparedRequest for reliable testing.
    """

    def __init__(self, response=None):
        self.response = response or MockHttpResponse()
        self.last_url = None

    def send(self, request, **kwargs):
        self.last_url = request.url
        self.response.url = request.url
        self.response._resp.request = request
        return self.response

    def close(self):
        pass
