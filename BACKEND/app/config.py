"""
config.py — Centralized Configuration v2

Perubahan dari v1:
- Tambah screenshots_dir
- Tambah cookie_file path
- Tambah direktori_url yang lebih fleksibel
- Chromium args lebih lengkap
- Headless default True (production-safe), override lewat .env
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project Root ─────────────────────────────────────────────────────────────
# config.py adalah di BACKEND/app/config.py
# BASE_DIR = BACKEND/
BASE_DIR = Path(__file__).resolve().parent.parent


# ─── Settings ────────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)
    cors_origins: str = Field(default="*")
    log_level: str = Field(default="INFO")

    # ── Database ──────────────────────────────────────────────────────────────
    db_path: str = Field(default=str(BASE_DIR / "data" / "mahkamah.db"))

    # ── Scraper ───────────────────────────────────────────────────────────────
    target_base_url: str = Field(
        default="https://putusan3.mahkamahagung.go.id"
    )
    # headless=False untuk development (manual Turnstile solve di jendela Chrome)
    # headless=True untuk production / Docker
    headless: bool = Field(default=True)
    browser_timeout: int = Field(default=30_000)
    min_delay: float = Field(default=2.0, ge=0.5)
    max_delay: float = Field(default=5.0, ge=1.0)
    scroll_delay_min: float = Field(default=0.3)
    scroll_delay_max: float = Field(default=1.2)
    max_retries: int = Field(default=3, ge=1, le=10)
    max_pages_per_search: int = Field(default=5, ge=1)
    request_timeout: int = Field(default=60)

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = Field(default=3600)

    # ── Paths ─────────────────────────────────────────────────────────────────
    log_dir: Path = Field(default=BASE_DIR / "logs")
    data_dir: Path = Field(default=BASE_DIR / "data")
    pdf_dir: Path = Field(default=BASE_DIR / "data" / "pdfs")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, v) -> bool:
        """Accept common non-boolean DEBUG values from global shells/tools."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod", ""}:
                return False
        return v

    @field_validator("max_delay")
    @classmethod
    def max_delay_gt_min(cls, v: float, info) -> float:
        min_d = info.data.get("min_delay", 2.0)
        if v <= min_d:
            raise ValueError("max_delay must be greater than min_delay")
        return v

    def model_post_init(self, __context) -> None:
        """Pastikan semua direktori yang dibutuhkan ada."""
        for d in [self.log_dir, self.data_dir, self.pdf_dir,
                  self.data_dir / "screenshots",
                  self.data_dir / "browser_profile"]:
            d.mkdir(parents=True, exist_ok=True)

        # Cookie directory di BACKEND/cookies/
        (BASE_DIR / "cookies").mkdir(parents=True, exist_ok=True)

    # ── URL Helpers ───────────────────────────────────────────────────────────

    @property
    def direktori_url(self) -> str:
        """URL halaman direktori putusan (target warmup)."""
        return f"{self.target_base_url}/direktori.html"

    @property
    def search_url(self) -> str:
        """URL halaman search."""
        return f"{self.target_base_url}/search.html"

    @property
    def cookie_file(self) -> Path:
        """Path file cookie JSON."""
        return BASE_DIR / "cookies" / "session.json"

    @property
    def screenshots_dir(self) -> Path:
        """Direktori untuk screenshot challenge."""
        return self.data_dir / "screenshots"

    @property
    def browser_profile_dir(self) -> Path:
        """Direktori persistent browser profile."""
        return self.data_dir / "browser_profile"


# ─── User-Agent Pool ─────────────────────────────────────────────────────────
# Chrome 124-125 di Windows/Mac/Linux — pool realistis
USER_AGENTS: List[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Safari Mac (lebih dipercaya Cloudflare)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


# ─── Stealth Chromium Launch Args ─────────────────────────────────────────────
CHROMIUM_ARGS: List[str] = [
    # ── Anti-detection ──────────────────────────────────────────────────────
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--disable-translate",

    # ── Performance & Stability ─────────────────────────────────────────────
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-ipc-flooding-protection",
    "--metrics-recording-only",
    "--mute-audio",

    # ── Network ─────────────────────────────────────────────────────────────
    "--ignore-certificate-errors",
    "--ignore-ssl-errors",
    "--allow-running-insecure-content",

    # ── Locale ──────────────────────────────────────────────────────────────
    "--lang=id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "--accept-lang=id-ID,id,en-US,en",

    # ── Sandbox / Memory ────────────────────────────────────────────────────
    "--disable-gpu-sandbox",
    "--disable-software-rasterizer",

    # ── Privacy/Fingerprint ─────────────────────────────────────────────────
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-web-security",                    # ← diperlukan untuk beberapa CF bypass
]


def get_random_user_agent() -> str:
    """Pilih user-agent secara acak dari pool."""
    return random.choice(USER_AGENTS)


# ─── Singleton ────────────────────────────────────────────────────────────────
settings = Settings()
