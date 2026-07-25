# events-scraper

A Python event scraping system with a database-first architecture, plugin-based
management commands, and a web interface for browsing events.

## Features

- Database-first architecture: SQLite with sub-millisecond queries
- Plugin-based commands: discover, add, and run management commands without
  touching the core
- Scraper packages: city or topic scrapers, either Python classes or YAML
  configs (AI-powered)
- Web interface: browse events, view status, manage subscriptions, ICS feeds
- Notification system: per-user event subscriptions delivered via plugins
  (Signal included)
- XDG config: user config lives at `$XDG_CONFIG_HOME/events_scraper/events.yaml`

## Layout

```
src/
  events_scraper/      # Library: scraper base, models, db, web app, config
  plugins/             # Plugin discovery (commands, notifiers)
  manage.py            # CLI entry: dispatches to plugins
```

## Install

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install .
```

After install, the `events` entrypoint is available:

```sh
events runserver --debug
events scrape paris
events help
```

In the repo, use `./manage.sh` as a drop-in replacement.

To run directly with the venv (e.g. from a systemd service):

```sh
/full/path/to/repo/.venv/bin/python src/manage.py runserver
```

## Quick start

Run the web server in debug mode:

```sh
./manage.sh runserver --debug
```

Scrape all groups except expensive ones:

```sh
./manage.sh scrape --groups-all --groups-exclude conferences --groups-exclude conferences_bitcoin
```

Scrape a specific group:

```sh
./manage.sh scrape paris
```

Scrape with detail fetching:

```sh
./manage.sh scrape paris --scrape-details
```

List available commands:

```sh
./manage.sh help
```

### Nuke

Destructive — wipes all events and cache immediately. Press Ctrl-C fast enough
or it's gone:

```console
$ ./manage.sh clear_cache && ./manage.sh delete_all
```

## Configuration

User config is read from
`$XDG_CONFIG_HOME/events_scraper/events.yaml` (default
`~/.config/events_scraper/events.yaml`). A default file is created the first
time the app runs. See `src/events_scraper/lib/config_template.py` for all
options with examples.

Minimal example:

```yaml
logging:
  level: WARNING

database:
  url: "sqlite:///$XDG_DATA_HOME/events_scraper/events.db"
```

## Adding a scraper

Scrapers live in scraper packages outside the repo. See `AGENTS.md` for the
full package development guide.

Packages are auto-discovered from:

- `$XDG_CONFIG_HOME/events_scraper/packages/<name>/`
- `$XDG_DATA_HOME/events_scraper/packages/<name>/`

Two package types are supported:

- **Python packages**: `scrapers/` directory with `BaseEventScraper` subclasses
- **Config-driven**: `configs/` directory with YAML files that drive the AI
  scraper

## Development

```sh
./test.sh                    # Full test suite (uses Docker)
./test.sh tests.lib.core     # Run a subset
```

Tests under `tests/` mirror the source layout. The test runner is Docker-based
to give a consistent environment; flake8 + coverage reports are emitted under
`reports/`.

## License

MIT — see `LICENSE`.
