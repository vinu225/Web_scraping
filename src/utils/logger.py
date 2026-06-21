"""
src/utils/logger.py
====================
Convenience helper for obtaining a named child logger.
All loggers are children of the root "news_scraper" logger configured
by ``config.logging_config.configure_logging``.
"""

from __future__ import annotations

import logging

from config.logging_config import configure_logging

# Ensure the root logger is initialised exactly once.
_ROOT_LOGGER = configure_logging("news_scraper")


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the ``news_scraper`` root.

    Parameters
    ----------
    name:
        Short identifier for the module, e.g. ``"duckduckgo"`` or ``"pipeline"``.

    Returns
    -------
    logging.Logger
        Ready-to-use logger that inherits handlers from the root logger.
    """
    return logging.getLogger(f"news_scraper.{name}")
