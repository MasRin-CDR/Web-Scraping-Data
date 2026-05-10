"""
config.py - Centralized Configuration Management
Mahkamah Agung Web Scraper
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project Root ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent


# ─── Settings Model ──────────────────────────────────────────────────────────
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=5432)
    db_name: str = Field(default="mahkamah_db")
    db_user: str = Field(default="postgres")
    db_password: str = Field(default="")

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def db_dsn_asyncpg(self) -> dict:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "database": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
        }

    # ── Scraper ───────────────────────────────────────────────────────────────
    target_url: str = Field(
        default="https://putusan3.mahkamahagung.go.id/direktori.html"
    )
    max_pages: int = Field(default=50, ge=1)
    concurrent_pages: int = Field(default=2, ge=1, le=5)
    request_timeout: int = Field(default=60, ge=10)

    # ── Delay (seconds) ───────────────────────────────────────────────────────
    min_delay: float = Field(default=2.5, ge=0.5)
    max_delay: float = Field(default=6.0, ge=1.0)
    scroll_delay_min: float = Field(default=0.5)
    scroll_delay_max: float = Field(default=1.5)

    @field_validator("max_delay")
    @classmethod
    def max_delay_must_exceed_min(cls, v: float, info) -> float:
        min_d = info.data.get("min_delay", 2.5)
        if v <= min_d:
            raise ValueError("max_delay must be greater than min_delay")
        return v

    # ── Retry ─────────────────────────────────────────────────────────────────
    max_retries: int = Field(default=5, ge=1, le=20)
    retry_backoff_base: float = Field(default=2.0)

    # ── Output ────────────────────────────────────────────────────────────────
    csv_output_dir: Path = Field(default=BASE_DIR / "output")
    log_dir: Path = Field(default=BASE_DIR / "logs")
    log_level: str = Field(default="INFO")

    # ── Browser ───────────────────────────────────────────────────────────────
    headless: bool = Field(default=False)
    browser_timeout: int = Field(default=30_000)  # ms

    def model_post_init(self, __context) -> None:
        """Ensure output directories exist."""
        self.csv_output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# ─── User-Agent Pool ─────────────────────────────────────────────────────────
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

# ─── Stealth Browser Args ─────────────────────────────────────────────────────
CHROMIUM_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-translate",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--metrics-recording-only",
    "--mute-audio",
    "--ignore-certificate-errors",
    "--lang=id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
]

# ─── Singleton ───────────────────────────────────────────────────────────────
settings = Settings()
