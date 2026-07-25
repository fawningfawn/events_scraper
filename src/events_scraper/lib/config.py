"""Configuration management for events application.

Handles loading and creation of YAML configuration files from XDG config directory.
"""

import logging
import re
import sys
from pathlib import Path
from typing import List
from typing import Optional

import xdg
import yaml

from events_scraper.lib.config_template import DEFAULT_CONFIG
from events_scraper.lib.constants import CONFIG_DIR_NAME
from events_scraper.lib.constants import DEFAULT_CONFIG_FILENAME

logger = logging.getLogger(__name__)


def xdg_config_home() -> Path:
    """Get XDG config home directory."""

    return Path(xdg.XDG_CONFIG_HOME)


def get_config_path() -> Path:
    """Get the path to the events configuration file."""
    return xdg_config_home() / CONFIG_DIR_NAME / DEFAULT_CONFIG_FILENAME


def get_default_group() -> str:
    try:
        config = load_config()
        val = config._config_data.get("default_group")
        if val:
            return val
    except Exception:
        pass
    return "paris"


class EventsConfig:
    """Configuration manager for events application."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config manager.

        Args:
            config_path: Optional custom config file path
        """
        self.config_path = config_path or get_config_path()
        self._config_data = {}
        logger.debug(f"Initializing config manager with path: {self.config_path}")
        self._load_config()
        # Log entire config object once after loading
        logger.debug(f"Loaded configuration: {self._config_data}")

    def _load_config(self):
        """Load configuration from file, creating default if needed."""
        if not yaml:
            # PyYAML not available, use empty config
            logger.warning("PyYAML not available, using empty configuration")
            self._config_data = {}
            return

        if not self.config_path.exists():
            logger.info(
                f"Config file does not exist at {self.config_path}, creating default"
            )
            self._create_default_config()
            self._config_data = {}
            return

        try:
            logger.debug(f"Loading configuration from {self.config_path}")
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config_data = yaml.safe_load(f) or {}
            logger.info(
                f"Successfully loaded configuration with {len(self._config_data)} top-level sections"
            )
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            # Always raise - invalid config should never be silently ignored
            raise

    def _create_default_config(self):
        """Create default configuration file with examples."""
        logger.debug(f"Creating config directory: {self.config_path.parent}")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG)
            logger.info(f"Created default config file: {self.config_path}")
            print(f"Created default config file: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to create config file {self.config_path}: {e}")
            print(f"Warning: Failed to create config file {self.config_path}: {e}")

    def _get_filter_section(self, section_name: str) -> dict:
        """Get filter section, safely handling nested structure."""
        filters_config = self._get_section_config("filters")
        return filters_config.get(section_name, {})

    def get_include_categories(self) -> List[str]:
        return self._get_filter_section("categories").get("include", [])

    def get_llm_provider(self) -> Optional[str]:
        return self._get_section_config("llm").get("provider")

    def get_llm_model(self) -> Optional[str]:
        return self._get_section_config("llm").get("model")

    def get_llm_api_key(self) -> Optional[str]:
        return self._get_section_config("llm").get("api_key")

    def get_exclude_categories(self) -> List[str]:
        """Get list of categories to exclude."""
        return self._get_filter_section("categories").get("exclude", [])

    def get_exclude_title_patterns(self) -> List[str]:
        """Get list of title patterns to exclude."""
        return self._get_filter_section("titles").get("exclude_patterns", [])

    def get_exclude_location_patterns(
        self, group: str = None, scraper: str = None
    ) -> List[str]:
        """Get list of location patterns to exclude.

        Args:
            group: Optional group name for per-group filtering
            scraper: Optional scraper name for per-scraper filtering

        Returns:
            List of location patterns to exclude (merged global + group + scraper)
        """
        patterns = self._get_filter_section("locations").get("exclude_patterns", [])

        # If group is specified, merge with group-specific patterns
        if group:
            by_group_config = self._get_filter_section("by_group").get(group, {})
            group_locations = by_group_config.get("locations", {})
            group_patterns = group_locations.get("exclude_patterns", [])
            # Union (both apply)
            patterns = list(set(patterns) | set(group_patterns))

        # If scraper is specified, merge with scraper-specific patterns
        if scraper:
            by_scraper_config = self._get_filter_section("by_scraper").get(scraper, {})
            scraper_locations = by_scraper_config.get("locations", {})
            scraper_patterns = scraper_locations.get("exclude_patterns", [])
            # Union (all apply)
            patterns = list(set(patterns) | set(scraper_patterns))

        return patterns

    def get_database_url(self) -> Optional[str]:
        """Get database URL from config."""
        return self._get_section_config("database").get("url")

    def get_log_level(self) -> str:
        """Get configured log level."""
        logging_config = self._get_section_config("logging")
        return logging_config.get("level", "WARNING")

    def get_log_file(self) -> Optional[str]:
        """Get configured log file path."""
        logging_config = self._get_section_config("logging")
        return logging_config.get("file")

    def get_log_format(self) -> str:
        """Get configured log format."""
        logging_config = self._get_section_config("logging")
        return logging_config.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Spinner animation config removed - using instant database loading

    def _get_section_config(self, section_name: str) -> dict:
        """Get config section safely, with type validation."""
        section_config = self._config_data.get(section_name, {})
        # Only validate if section exists - missing sections get empty dict default
        if section_name in self._config_data and not isinstance(section_config, dict):
            # Print error and exit immediately - don't raise exception to be caught elsewhere
            config_path = get_config_path()
            print(
                f"Error in config file: Config section '{section_name}' must be a dictionary, not {type(section_config).__name__}"
            )
            print("")
            print(f"Your config file at {config_path} appears to be malformed.")
            print("To fix this issue, you can:")
            print(
                f"  1. Move the config file out of the way: mv {config_path} {config_path}.backup"
            )
            print("  2. Run the application again to create a fresh config file")
            print("  3. Copy your settings from the backup to the new file")
            print("")
            sys.exit(1)
        return section_config

    def should_include_event(
        self, title: str, category: str = None, location: str = None
    ) -> bool:
        """Check if an event should be included based on config rules.

        Args:
            title: Event title to check
            category: Event category to check (optional)
            location: Event location to check (optional)

        Returns:
            True if event should be included, False otherwise
        """
        logger.debug(
            f"Checking if event should be included - Title: '{title}', Category: '{category}', Location: '{location}'"
        )

        # Check category filtering first
        if category:
            include_cats = self.get_include_categories()
            exclude_cats = self.get_exclude_categories()

            # If include list exists and category not in it, exclude
            if include_cats and category not in include_cats:
                logger.debug(
                    f"Event excluded - category '{category}' not in include list: {include_cats}"
                )
                return False

            # If category is in exclude list, exclude
            if exclude_cats and category in exclude_cats:
                logger.debug(
                    f"Event excluded - category '{category}' is in exclude list: {exclude_cats}"
                )
                return False

        # Check title pattern filtering
        exclude_patterns = self.get_exclude_title_patterns()

        # Check exclude patterns (if title matches any, exclude)
        for pattern in exclude_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                logger.debug(
                    f"Event excluded - title '{title}' matches exclude pattern '{pattern}'"
                )
                return False

        # Check location pattern filtering
        if location:
            location_patterns = self.get_exclude_location_patterns()
            for pattern in location_patterns:
                if re.search(pattern, location, re.IGNORECASE):
                    logger.debug(
                        f"Event excluded - location '{location}' matches exclude pattern '{pattern}'"
                    )
                    return False

        logger.debug("Event included - passed all filter checks")
        return True


def apply_config_filters(
    event_collection,
    config: EventsConfig = None,
    cli_include_categories: List[str] = None,
    cli_exclude_categories: List[str] = None,
    cli_exclude_titles: List[str] = None,
    filters_enabled: bool = True,
    group: str = None,
    scraper: str = None,
):
    """Apply configuration and CLI filters to an event collection.

    CLI arguments take precedence over config file settings.

    Args:
        event_collection: EventCollection to filter
        config: EventsConfig instance (loads default if None)
        cli_include_categories: CLI category include list (overrides config)
        cli_exclude_categories: CLI category exclude list (overrides config)
        cli_exclude_titles: CLI title exclude list (overrides config)
        filters_enabled: Whether to apply filters at all (default True)
        group: Optional group name for per-group filtering
        scraper: Optional scraper name for per-scraper filtering

    Returns:
        Filtered EventCollection
    """
    logger.debug(
        f"Applying filters - enabled: {filters_enabled}, starting events: {len(event_collection.events)}"
    )

    # If filters are disabled, return unfiltered collection
    if not filters_enabled:
        logger.info("Filters disabled, returning unfiltered event collection")
        return event_collection

    if config is None:
        config = load_config()

    # Apply category filtering - CLI overrides config
    exclude_categories = cli_exclude_categories or config.get_exclude_categories()
    if exclude_categories:
        logger.debug(f"Applying exclude categories filter: {exclude_categories}")
        initial_count = len(event_collection.events)
        event_collection = event_collection.exclude_categories(exclude_categories)
        logger.debug(
            f"Exclude categories filter: {initial_count} -> {len(event_collection.events)} events"
        )

    include_categories = cli_include_categories or config.get_include_categories()
    if include_categories:
        logger.debug(f"Applying include categories filter: {include_categories}")
        initial_count = len(event_collection.events)
        event_collection = event_collection.include_categories(include_categories)
        logger.debug(
            f"Include categories filter: {initial_count} -> {len(event_collection.events)} events"
        )

    # Apply title filtering - CLI overrides config
    exclude_titles = cli_exclude_titles or config.get_exclude_title_patterns()
    if exclude_titles:
        logger.debug(f"Applying exclude titles filter: {exclude_titles}")
        initial_count = len(event_collection.events)
        event_collection = event_collection.exclude_titles(exclude_titles)
        logger.debug(
            f"Exclude titles filter: {initial_count} -> {len(event_collection.events)} events"
        )

    # Apply location filtering
    exclude_locations = config.get_exclude_location_patterns(
        group=group, scraper=scraper
    )
    if exclude_locations:
        logger.debug(f"Applying exclude locations filter: {exclude_locations}")
        initial_count = len(event_collection.events)
        event_collection = event_collection.exclude_locations(exclude_locations)
        logger.debug(
            f"Exclude locations filter: {initial_count} -> {len(event_collection.events)} events"
        )

    logger.info(
        f"Filtering complete - final event count: {len(event_collection.events)}"
    )
    return event_collection


def load_config(config_path: Optional[Path] = None) -> EventsConfig:
    """Load events configuration.

    Args:
        config_path: Optional custom config file path

    Returns:
        EventsConfig instance
    """
    logger.debug(f"Loading configuration from path: {config_path or 'default'}")
    config = EventsConfig(config_path)
    logger.debug("Configuration loaded successfully")
    return config
