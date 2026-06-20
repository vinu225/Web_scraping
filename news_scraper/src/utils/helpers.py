"""
src/utils/helpers.py
=====================
Miscellaneous utility functions shared across modules.
"""

from __future__ import annotations

import re
import time
from functools import wraps
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------


def retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Exponential-backoff retry decorator.

    Parameters
    ----------
    max_attempts:
        Total number of attempts (including the first try).
    backoff:
        Multiplier applied to the wait time after each failure.
    exceptions:
        Exception types that trigger a retry; others propagate immediately.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            wait = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    time.sleep(wait)
                    wait *= backoff

        return wrapper  # type: ignore[return-value]

    return decorator


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def is_valid_url(url: str) -> bool:
    """Return ``True`` if *url* has a valid HTTP/HTTPS scheme and netloc."""
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def clean_url(url: str) -> str:
    """Strip surrounding whitespace and trailing slashes from a URL."""
    return url.strip().rstrip("/")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def truncate(text: str, max_chars: int = 500, suffix: str = "…") -> str:
    """Truncate *text* to *max_chars* characters, appending *suffix* if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + suffix


def count_words(text: str) -> int:
    """Return the word count of a text string."""
    return len(re.findall(r"\b\w+\b", text))


def estimate_reading_time(word_count: int, wpm: int = 200) -> float:
    """Estimate reading time in minutes given a word count."""
    return round(word_count / wpm, 1)


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------


class Timer:
    """Simple wall-clock timer usable as a context manager."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
