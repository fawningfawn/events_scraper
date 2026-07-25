"""
Logging setup and configuration
"""

import logging
import sys


def setup_logging(
    verbose_level: int = 0,
    log_level: str = None,
    log_file: str = None,
    config=None,
    log_stream=None,
):
    """Setup logging configuration based on CLI args and config file.

    Priority: CLI args > config file > defaults

    Args:
        verbose_level: Legacy verbose level (for backward compatibility)
        log_level: Explicit log level string (overrides verbose_level and config)
        log_file: Log file path (overrides config)
        config: EventsConfig instance for reading config file settings
        log_stream: Explicit stream object for console logging
    """
    level = _determine_log_level(log_level, verbose_level, config)
    log_destination = _determine_log_destination(log_file, config)
    log_format = _determine_log_format(config)

    _configure_logging(level, log_destination, log_format, log_stream=log_stream)

    # Set up module-specific loggers
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging configured: level={logging.getLevelName(level)}, file={log_destination}"
    )


def _determine_log_level(log_level: str, verbose_level: int, config) -> int:
    """Determine the log level based on inputs."""
    if log_level:
        try:
            return getattr(logging, log_level.upper())
        except AttributeError:
            print(f"Warning: Invalid log level '{log_level}', using WARNING")
            return logging.WARNING
    elif verbose_level > 0:
        log_levels = {
            0: logging.WARNING,
            1: logging.INFO,
            2: logging.DEBUG,
            3: logging.DEBUG,
        }
        return log_levels.get(verbose_level, logging.DEBUG)
    elif config:
        try:
            return getattr(logging, config.get_log_level().upper())
        except AttributeError:
            return logging.WARNING
    else:
        return logging.CRITICAL + 1


def _determine_log_destination(log_file: str, config) -> str:
    """Determine the log destination file."""
    if log_file:
        return log_file
    elif config and config.get_log_file():
        return config.get_log_file()
    else:
        return None


def _determine_log_format(config) -> str:
    """Determine the log format string."""
    if config:
        return config.get_log_format()
    else:
        # Include file:line and thread ID in format for debugging
        return "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - [Thread %(thread)d] - %(message)s"


def _configure_logging(
    level: int, log_destination: str, log_format: str, log_stream=None
):
    """Configure the logging system with determined parameters."""
    if log_stream is not None:
        logging.basicConfig(level=level, format=log_format, stream=log_stream)
        return

    if log_destination:
        logging.basicConfig(
            level=level, format=log_format, filename=log_destination, filemode="a"
        )
    elif level <= logging.CRITICAL:
        # Use stdout for verbose logging so users can pipe output
        logging.basicConfig(level=level, format=log_format, stream=sys.stdout)
