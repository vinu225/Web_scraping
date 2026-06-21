"""
config/logging_config.py
========================
Structured logging configuration.
Provides a rotating file handler for both general and error logs,
plus a coloured console handler for interactive sessions.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from config.settings import settings

# ------------------------------------------------------------------
# ANSI colour codes for console output
# ------------------------------------------------------------------
_COLOURS = {
    "DEBUG": "\033[36m",     # Cyan
    "INFO": "\033[32m",      # Green
    "WARNING": "\033[33m",   # Yellow
    "ERROR": "\033[31m",     # Red
    "CRITICAL": "\033[35m",  # Magenta
    "RESET": "\033[0m",
}


class ColouredFormatter(logging.Formatter):
    """Adds ANSI colour to log-level names in console output."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        colour = _COLOURS.get(record.levelname, _COLOURS["RESET"])
        reset = _COLOURS["RESET"]
        record.levelname = f"{colour}{record.levelname:<8}{reset}"
        return super().format(record)


def configure_logging(name: str = "news_scraper") -> logging.Logger:
    """
    Set up and return the root application logger.

    Parameters
    ----------
    name:
        Logger name (defaults to ``news_scraper``).

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    log_dir: Path = settings.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(settings.log_level.upper())

    if logger.handlers:
        return logger  # Already configured — avoid duplicate handlers

    fmt_detailed = "%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(lineno)d | %(message)s"
    fmt_simple = "%(asctime)s | %(levelname)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    # ------------------------------------------------------------------
    # Console handler — coloured, INFO+
    # ------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(
        ColouredFormatter(fmt=fmt_simple, datefmt=date_fmt)
    )

    # ------------------------------------------------------------------
    # Rotating file handler — scraper.log (all levels)
    # ------------------------------------------------------------------
    general_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "scraper.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    general_handler.setLevel(logging.DEBUG)
    general_handler.setFormatter(
        logging.Formatter(fmt=fmt_detailed, datefmt=date_fmt)
    )

    # ------------------------------------------------------------------
    # Rotating file handler — error.log (WARNING+)
    # ------------------------------------------------------------------
    error_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(
        logging.Formatter(fmt=fmt_detailed, datefmt=date_fmt)
    )

    logger.addHandler(console_handler)
    logger.addHandler(general_handler)
    logger.addHandler(error_handler)

    return logger
