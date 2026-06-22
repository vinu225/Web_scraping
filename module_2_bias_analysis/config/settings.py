"""
Centralized configuration: model path/name, device, chunk size, thresholds.

All tunables live here so the rest of the codebase never hardcodes magic
numbers. Values are read from environment variables / a `.env` file via
pydantic-settings (prefix `BIAS_`), with sane defaults so the module works
out of the box in dev mode.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration for the bias analysis module."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BIAS_", extra="ignore")

    # --- Model ---------------------------------------------------------------
    model_name: str = "roberta-base"
    # Path to a fine-tuned bias-classification checkpoint. If empty, the
    # base RoBERTa is loaded with a fresh (untrained) classification head —
    # functionally correct end-to-end, but predictions will be uninformative
    # until a fine-tuned checkpoint is supplied.
    model_path: Optional[str] = None
    num_labels: int = 2  # index 1 = "biased"
    device: str = "auto"  # "auto" | "cpu" | "cuda" | "cuda:0" ...

    # --- Sequence handling -----------------------------------------------------
    max_seq_length: int = 512
    chunk_stride: int = 128  # token overlap between consecutive sliding-window chunks
    inference_batch_size: int = 8

    # --- Score combination weights -----------------------------------------------
    # final_bias_score = model_weight * model_score + feature_weight * feature_score
    model_weight: float = 0.7
    feature_weight: float = 0.3

    # --- Classification thresholds (inclusive upper bounds) ------------------------
    low_bias_max: float = 0.25
    moderate_bias_max: float = 0.50
    high_bias_max: float = 0.75
    # anything above high_bias_max -> "Extreme Bias"

    # --- Validation --------------------------------------------------------------
    min_content_length_chars: int = 50

    # --- Logging -------------------------------------------------------------------
    log_level: str = "INFO"
    log_file: str = "module_2_bias_analysis/bias_analysis.log"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


__all__ = ["Settings", "get_settings"]
