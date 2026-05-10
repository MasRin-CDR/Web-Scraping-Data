"""
utils/helpers.py - Shared Utility Functions
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from config import USER_AGENTS, settings


# ─── Delay Utilities ─────────────────────────────────────────────────────────

async def random_delay(
    min_sec: Optional[float] = None,
    max_sec: Optional[float] = None,
) -> None:
    """Sleep for a random duration to mimic human behavior."""
    lo = min_sec if min_sec is not None else settings.min_delay
    hi = max_sec if max_sec is not None else settings.max_delay
    delay = random.uniform(lo, hi)
    await asyncio.sleep(delay)


async def typing_delay() -> None:
    """Short delay simulating typing between keystrokes."""
    await asyncio.sleep(random.uniform(0.05, 0.25))


# ─── User-Agent ───────────────────────────────────────────────────────────────

def get_random_user_agent() -> str:
    """Return a random desktop browser user-agent string."""
    return random.choice(USER_AGENTS)


# ─── URL Helpers ─────────────────────────────────────────────────────────────

def normalize_url(base: str, href: str) -> str:
    """Resolve a potentially relative URL against a base URL."""
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base, href)


def is_pdf_url(url: str) -> bool:
    """Check if a URL points to a PDF resource."""
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf") or "pdf" in parsed.query.lower()


# ─── Date Parsing ─────────────────────────────────────────────────────────────

MONTH_ID: dict[str, int] = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def parse_indonesian_date(text: str) -> Optional[datetime]:
    """
    Parse Indonesian-language date strings.
    Handles formats like:
      - "12 Januari 2024"
      - "01/03/2024"
      - "2024-03-01"
    """
    if not text:
        return None

    text = text.strip()

    # Try ISO format first
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    # Try Indonesian month names
    lower = text.lower()
    for month_name, month_num in MONTH_ID.items():
        if month_name in lower:
            cleaned = re.sub(month_name, f"{month_num:02d}", lower)
            parts = re.findall(r"\d+", cleaned)
            if len(parts) >= 3:
                try:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return datetime(year, month, day)
                except ValueError:
                    pass

    return None


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text: Optional[str]) -> str:
    """Strip and normalize whitespace from a string."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_case_number(title: str) -> Optional[str]:
    """
    Extract case/register number from a putusan title.
    Example: "123/Pdt.G/2023/PN.Jkt.Pst"
    """
    pattern = r"\d+/[A-Za-z.]+/\d{4}/[A-Za-z.]+"
    match = re.search(pattern, title)
    return match.group(0) if match else None


# ─── Chunking ─────────────────────────────────────────────────────────────────

def chunked(lst: list[Any], size: int):
    """Yield successive `size`-sized chunks from `lst`."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]
