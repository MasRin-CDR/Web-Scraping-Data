"""
config.py — Centralized Configuration
Loads environment variables via pydantic-settings with sensible defaults.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project Root ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # BACKEND/


# ─── Settings ────────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    cors_origins: str = Field(default="*")

    # ── Database (SQLite by default) ──────────────────────────────────────────
    db_path: str = Field(default=str(BASE_DIR / "data" / "mahkamah.db"))

    # ── Scraper ───────────────────────────────────────────────────────────────
    target_base_url: str = Field(
        default="https://putusan3.mahkamahagung.go.id"
    )
    headless: bool = Field(default=False)
    browser_timeout: int = Field(default=30_000)
    min_delay: float = Field(default=2.0, ge=0.5)
    max_delay: float = Field(default=5.0, ge=1.0)
    scroll_delay_min: float = Field(default=0.3)
    scroll_delay_max: float = Field(default=1.2)
    max_retries: int = Field(default=3, ge=1, le=10)
    max_pages_per_search: int = Field(default=5, ge=1)
    request_timeout: int = Field(default=60)

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = Field(default=3600)  # 1 hour

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=BASE_DIR / "logs")

    # ── Output ────────────────────────────────────────────────────────────────
    data_dir: Path = Field(default=BASE_DIR / "data")
    pdf_dir: Path = Field(default=BASE_DIR / "data" / "pdfs")

    @field_validator("max_delay")
    @classmethod
    def max_delay_gt_min(cls, v: float, info) -> float:
        min_d = info.data.get("min_delay", 2.0)
        if v <= min_d:
            raise ValueError("max_delay must be greater than min_delay")
        return v

    def model_post_init(self, __context) -> None:
        """Ensure directories exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)

    @property
    def direktori_url(self) -> str:
        return f"{self.target_base_url}/direktori.html"

    @property
    def search_url(self) -> str:
        return f"{self.target_base_url}/search.html"


# ─── User-Agent Pool ─────────────────────────────────────────────────────────
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# ─── Stealth Chromium Args ────────────────────────────────────────────────────
CHROMIUM_ARGS: List[str] = [
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


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


# ─── Singleton ────────────────────────────────────────────────────────────────
settings = Settings()
