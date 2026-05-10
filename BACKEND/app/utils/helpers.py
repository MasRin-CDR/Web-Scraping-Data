"""
utils/helpers.py — Shared Utility Functions
Date parsing, URL handling, text cleaning, delay helpers.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, quote

from app.config import settings, USER_AGENTS


# ─── Delay ────────────────────────────────────────────────────────────────────

async def random_delay(
    min_sec: Optional[float] = None,
    max_sec: Optional[float] = None,
) -> None:
    """Sleep for a random duration to mimic human timing."""
    lo = min_sec if min_sec is not None else settings.min_delay
    hi = max_sec if max_sec is not None else settings.max_delay
    await asyncio.sleep(random.uniform(lo, hi))


async def short_delay() -> None:
    """Quick micro-delay (50-250 ms)."""
    await asyncio.sleep(random.uniform(0.05, 0.25))


# ─── User-Agent ───────────────────────────────────────────────────────────────

def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


# ─── URL ──────────────────────────────────────────────────────────────────────

def normalize_url(base: str, href: str) -> str:
    """Resolve a relative URL against a base URL."""
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    return urljoin(base, href)


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf") or "pdf" in parsed.query.lower()


def build_search_url(
    base_url: str,
    keyword: str = "",
    lokasi: str = "",
    jenis: str = "",
    page: int = 1,
) -> str:
    """Construct the search URL for putusan3.mahkamahagung.go.id."""
    if keyword:
        url = f"{base_url}/search.html?q={quote(keyword)}"
        if page > 1:
            url += f"&page={page}"
        return url
    # Default: directory listing
    url = f"{base_url}/direktori.html"
    if page > 1:
        url += f"?page={page}"
    return url


# ─── Date Parsing ─────────────────────────────────────────────────────────────

MONTH_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
    # Abbreviations
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "agu": 8, "ags": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
}


def parse_indonesian_date(text: str) -> Optional[str]:
    """
    Parse Indonesian-language date strings into ISO format (YYYY-MM-DD).
    Handles: '12 Januari 2024', '01/03/2024', '2024-03-01'.
    """
    if not text:
        return None

    text = text.strip()

    # ISO / slash / dash formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Indonesian month names
    lower = text.lower()
    for month_name, month_num in MONTH_ID.items():
        if month_name in lower:
            cleaned = re.sub(month_name, str(month_num), lower)
            parts = re.findall(r"\d+", cleaned)
            if len(parts) >= 3:
                try:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    if year < 100:
                        year += 2000
                    return datetime(year, month, day).strftime("%Y-%m-%d")
                except ValueError:
                    pass

    return None


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def clean_text(text: Optional[str]) -> str:
    """Strip and normalize whitespace."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_case_number(title: str) -> Optional[str]:
    """Extract case number like '123/Pdt.G/2023/PN.Jkt.Pst'."""
    pattern = r"\d+/[A-Za-z.]+/\d{4}/[A-Za-z.]+"
    match = re.search(pattern, title)
    return match.group(0) if match else None


def extract_year(text: str) -> Optional[str]:
    """Extract a 4-digit year from text."""
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else None
