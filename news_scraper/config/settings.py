"""
config/settings.py
==================
Centralized application settings loaded from environment variables via pydantic-settings.
All runtime configuration lives here; no magic strings elsewhere in the codebase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: two levels up from this file (news_scraper/)
BASE_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide settings resolved from .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # NewsAPI
    # ------------------------------------------------------------------
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")

    # ------------------------------------------------------------------
    # MongoDB (optional)
    # ------------------------------------------------------------------
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="news_scraper", alias="MONGODB_DB_NAME")
    mongodb_collection: str = Field(default="articles", alias="MONGODB_COLLECTION")

    # ------------------------------------------------------------------
    # HTTP Client
    # ------------------------------------------------------------------
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    retry_backoff: float = Field(default=2.0, alias="RETRY_BACKOFF")
    rate_limit_delay: float = Field(default=1.0, alias="RATE_LIMIT_DELAY")
    max_workers: int = Field(default=5, alias="MAX_WORKERS")

    # ------------------------------------------------------------------
    # DuckDuckGo
    # ------------------------------------------------------------------
    ddg_max_results: int = Field(default=50, alias="DDG_MAX_RESULTS")
    ddg_region: str = Field(default="wt-wt", alias="DDG_REGION")
    ddg_safesearch: str = Field(default="moderate", alias="DDG_SAFESEARCH")

    # ------------------------------------------------------------------
    # Data Directories
    # ------------------------------------------------------------------
    raw_data_dir: Path = Field(default=BASE_DIR / "data" / "raw", alias="RAW_DATA_DIR")
    cleaned_data_dir: Path = Field(
        default=BASE_DIR / "data" / "cleaned", alias="CLEANED_DATA_DIR"
    )
    failed_data_dir: Path = Field(
        default=BASE_DIR / "data" / "failed", alias="FAILED_DATA_DIR"
    )
    exports_dir: Path = Field(default=BASE_DIR / "data" / "exports", alias="EXPORTS_DIR")
    log_dir: Path = Field(default=BASE_DIR / "logs", alias="LOG_DIR")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_max_bytes: int = Field(default=10_485_760, alias="LOG_MAX_BYTES")  # 10 MB
    log_backup_count: int = Field(default=5, alias="LOG_BACKUP_COUNT")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("raw_data_dir", "cleaned_data_dir", "failed_data_dir", "exports_dir", "log_dir", mode="before")
    @classmethod
    def ensure_absolute(cls, v: str | Path) -> Path:
        p = Path(v)
        return p if p.is_absolute() else BASE_DIR / p

    def ensure_dirs(self) -> None:
        """Create all required directories if they do not exist."""
        for attr in (
            "raw_data_dir",
            "cleaned_data_dir",
            "failed_data_dir",
            "exports_dir",
            "log_dir",
        ):
            path: Path = getattr(self, attr)
            path.mkdir(parents=True, exist_ok=True)


# Singleton instance used throughout the application
settings = Settings()
settings.ensure_dirs()
