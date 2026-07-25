# AGENTS.md

Guide for agents working on this project.

## Project Overview

A Python event scraping system with a database-first architecture:

- **Database-First Architecture**: SQLite-based single source of truth
- **Modular Design**: `lib/` library, `plugins/` command + notifier
  registries, `packages/` for city/topic scrapers
- **Smart Geocoding**: SQLite-cached geocoding with intelligent fallbacks
- **Web Interface**: Flask-based browser UI for events, status, subscriptions
- **Extensible**: Abstract base classes plus dynamic loading for new
  scrapers, commands, and notifiers
- **Comprehensive Testing**: 700+ unit tests, coverage reports under
  `reports/coverage/`

### Core Components

| Component | Location | Purpose |
|---|---|---|
| Base scraper + Event models | `lib/core/` | `BaseEventScraper`, `Event`, `EventCollection`, ORM, geocoding |
| Scraper variants | `lib/scrapers/` | AI scraper, hybrid scraper, YAML conference scrapers |
| Package discovery | `lib/packages.py` + `lib/scraper_meta.py` | Auto-discover scraper packages |
| Web + API + ICS | `lib/web/` | Flask app, REST API, ICS feeds |
| Subscriptions | `lib/subscriptions/` | Per-user keyword subscriptions + notifications |
| CLI entry point | `src/manage.py` + `./manage.sh` | Plugin-driven command interface |

### Dependencies

Install with: `pip install -r requirements.txt`

## Development Workflow

### Testing
- `bash test.sh [python_module ...]` runs the test suite in Docker
- Always run `bash test.sh` before committing
- HTML coverage reports are generated in `reports/coverage/`

### Dependencies
- **Always add new dependencies to `requirements.in`**: update `requirements.in`
  with proper comments explaining their purpose

## Package Development

Scraper packages are the primary extension mechanism. Packages live outside the
repo and are auto-discovered at runtime:

- `$XDG_CONFIG_HOME/events_scraper/packages/<name>/`
- `$XDG_DATA_HOME/events_scraper/packages/<name>/`

During development, packages can also be placed in `src/packages/<name>/` for
convenience, but they should never be committed.

### Concepts

| Term | Definition |
|---|---|
| **scraper** | A Python class or YAML config that fetches events from one source |
| **package** | A directory containing scrapers, configs, tests, commands, and metadata |
| **group** | The primary grouping key throughout the system, derived from package metadata (replaced the older `city` term) |
| **nav section** | Page-level grouping in the web UI; multiple groups can belong to one nav section |
| **city** | A kind of group; package metadata uses `SUPPORTED_CITIES` since each city can be its own group |

### Package Types

There are two kinds of packages:

#### Python Packages (city/topic scrapers)

Used when scrapers need custom parsing logic. Each scraper is a Python class
extending `BaseEventScraper`.

**Directory structure:**
```
<name>/
├── __init__.py              (empty)
└── scrapers/
    ├── __init__.py          (exports get_scrapers())
    ├── metadata.py          (package metadata)
    ├── <scraper>.py         (individual scraper classes)
    └── tests/               (optional)
```

**`scrapers/__init__.py`** — two patterns are used:

*Auto-discovery* (recommended for many scrapers):
```python
import os
from events_scraper.lib.module_loader import load_classes_from_package

def get_scrapers():
    return load_classes_from_package(os.path.dirname(__file__), "EventScraper")
```

*Explicit list* (when you need control over order or filtering):
```python
from .oper_scraper import OperScraper
from .club_scraper import ClubScraper

def get_scrapers():
    return [OperScraper, ClubScraper]
```

**`scrapers/metadata.py`** — defines package-level metadata:
```python
WEIGHT = 10                     # Display ordering (lower = first)
NAV_LABEL = "Paris"            # Optional: nav label override
NAV_SECTION = "Events"          # Optional: nav grouping
SUPPORTED_CITIES = ["paris"]   # City/group identifiers
```

`SUPPORTED_CITIES` can be a list of strings or a list of dicts with
`name`, `aliases`, and `display_name` keys.

**Scraper class contract** — every scraper must:
- Extend `BaseEventScraper` (from `lib/core/scraper.py`)
- Implement `scraper_name` property (e.g. `"paris.oper"`)
- Implement `fetch(target_date)` returning an `EventCollection`

The `Event` dataclass fields:
| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | `str` | Yes | Event title |
| `date` | `date \| str` | Yes | `date` object or `"YYYY-MM-DD"` |
| `time` | `time \| str` | No | Start time |
| `location` | `str` | No | Venue name |
| `categories` | `List[str]` | No | E.g. `["Music", "Jazz"]` |
| `detail_url` | `str` | No | Link to event detail page |
| `scraper` | `str` | No | Auto-set by framework |
| `cancelled` | `bool` | No | Default `False` |
| `end_date` | `date \| str` | No | For multi-day events |

See `lib/core/models.py` for the full `Event` definition and
`lib/core/scraper.py` for the `BaseEventScraper` class.

**Key `BaseEventScraper` hooks to override:**
- `get_event_containers(soup)` → `List[Tag]` — split page into event elements
- `extract_event_from_container(container, target_date)` → `Event` — parse one container
- `find_next_page_url(soup, current_url)` → `str | None` — pagination
- `fetch(target_date)` → `EventCollection` — override for custom fetch logic
- `fetch_date_range(start, end)` → `EventCollection` — multi-day fetching

**Helper utilities** (see `lib/core/scraper.py`):
- `http_get(url)` — cached HTTP GET with browser headers
- `BROWSER_HEADERS` — standard User-Agent/Accept headers

#### Config-Driven Packages (conference scrapers)

Used for simple conference/event pages that can be parsed by the AI scraper.
No Python code needed — just YAML config files.

**Directory structure:**
```
<name>/
├── __init__.py              (empty)
└── configs/
    ├── meta.yaml            (group metadata)
    └── <scraper>.yaml       (individual conference configs)
```

**`configs/meta.yaml`:**
```yaml
group: conferences
display_name: Conferences
weight: 20
feed_enabled: true
show_date: all
hide_from_status: false
```

**Individual scraper `.yaml`:**
```yaml
scraper_name: unique-identifier
base_url: https://example.com/
events_url: https://example.com/events  # Optional if different from base_url
categories:
  - crypto
  - mining
multiple_events: false  # Set true if page lists multiple events
```

**URL variable expansion** (handled by config processor):
- `{year}` → 4-digit year (2025, 2026, ...)
- `{yy}` → 2-digit year (25, 26, ...)

### Adding a New Python Package

1. Create the directory structure as shown above
2. Write one or more scraper classes extending `BaseEventScraper`
3. Add `scrapers/__init__.py` with `get_scrapers()`
4. Add `scrapers/metadata.py` with `WEIGHT` and `SUPPORTED_CITIES`
5. Write tests in `scrapers/tests/`
6. Run `bash test.sh` to verify

### Adding a New Config-Driven Package

1. Create `configs/meta.yaml` with group metadata
2. Add individual `<scraper>.yaml` files for each conference
3. No code changes needed — configs are auto-loaded
