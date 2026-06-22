"""
Tracks loading, preprocessing, inference, scoring, and total execution times.

Provides:
- `get_logger(name)`: a configured logger (console + rotating file handler).
- `StageTimer`: a context manager that times a block of code and logs the
  duration at DEBUG level, while also recording it into a shared
  `PipelineTimings` accumulator so the final API response can report
  per-stage timings as required by the spec.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator, Optional

from module_2_bias_analysis.config.settings import get_settings

_CONFIGURED_LOGGERS: set[str] = set()


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger configured once per process."""
    settings = get_settings()
    logger = logging.getLogger(name)

    if name in _CONFIGURED_LOGGERS:
        return logger

    logger.setLevel(settings.log_level.upper())
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Filesystem may be read-only (e.g. some container setups) — console
        # logging alone is acceptable in that case.
        logger.warning("Could not open log file '%s'; logging to console only.", settings.log_file)

    _CONFIGURED_LOGGERS.add(name)
    return logger


@dataclass
class PipelineTimings:
    """Accumulates stage-by-stage durations for a single pipeline run."""

    loading_time_seconds: float = 0.0
    preprocessing_time_seconds: float = 0.0
    inference_time_seconds: float = 0.0
    scoring_time_seconds: float = 0.0
    total_time_seconds: float = 0.0
    _stage_start: float = field(default=0.0, repr=False, compare=False)

    def as_dict(self) -> dict:
        return {
            "loading_time_seconds": round(self.loading_time_seconds, 4),
            "preprocessing_time_seconds": round(self.preprocessing_time_seconds, 4),
            "inference_time_seconds": round(self.inference_time_seconds, 4),
            "scoring_time_seconds": round(self.scoring_time_seconds, 4),
            "total_time_seconds": round(self.total_time_seconds, 4),
        }


@contextmanager
def StageTimer(
    stage_name: str,
    logger: Optional[logging.Logger] = None,
    timings: Optional[PipelineTimings] = None,
) -> Iterator[None]:
    """
    Context manager that times a pipeline stage.

    Usage:
        timings = PipelineTimings()
        with StageTimer("preprocessing", logger, timings):
            do_preprocessing()
        # timings.preprocessing_time_seconds is now populated
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if logger is not None:
            logger.debug("Stage '%s' completed in %.4fs", stage_name, elapsed)
        if timings is not None:
            attr = f"{stage_name}_time_seconds"
            if hasattr(timings, attr):
                setattr(timings, attr, getattr(timings, attr) + elapsed)


__all__ = ["get_logger", "PipelineTimings", "StageTimer"]
