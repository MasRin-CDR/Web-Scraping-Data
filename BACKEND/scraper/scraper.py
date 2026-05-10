"""
scraper/scraper.py - Main Scraper Orchestrator
Coordinates browser, parsing, retries, and output writing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from database.csv_writer import CSVWriter
from database.db import db
from database.models import PutusanRecord
from scraper.browser import BrowserManager
from scraper.human_simulation import HumanSimulator
from scraper.parser import DirectoriParser
from utils.helpers import random_delay
from utils.logger import log


class MahkamahScraper:
    """
    Production-grade async scraper for Mahkamah Agung direktori.

    Features:
    - Stealth Chromium with human simulation
    - Auto-retry with exponential backoff
    - Async pagination handling
    - Dual output: PostgreSQL + CSV
    - Session cookie persistence
    - Graceful shutdown on interrupt
    """

    def __init__(
        self,
        use_db: bool = True,
        use_csv: bool = True,
        max_pages: Optional[int] = None,
    ) -> None:
        self._browser = BrowserManager()
        self._parser = DirectoriParser()
        self._csv = CSVWriter() if use_csv else None
        self._use_db = use_db
        self._use_csv = use_csv
        self._max_pages = max_pages or settings.max_pages
        self._stats = {
            "pages_scraped": 0,
            "records_extracted": 0,
            "records_saved": 0,
            "errors": 0,
            "start_time": 0.0,
        }

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize browser and database connections."""
        log.info("=" * 60)
        log.info("Mahkamah Agung Scraper starting")
        log.info("Target: {}", settings.target_url)
        log.info("Max pages: {}", self._max_pages)
        log.info("=" * 60)

        await self._browser.start()

        if self._use_db:
            await db.connect()

        self._stats["start_time"] = time.time()

    async def stop(self) -> None:
        """Save session, close connections, print summary."""
        await self._browser.save_cookies()

        if self._use_db:
            await db.disconnect()

        elapsed = time.time() - self._stats["start_time"]
        log.info("=" * 60)
        log.info("Scraping complete | elapsed={:.1f}s", elapsed)
        log.info("Pages scraped:    {}", self._stats["pages_scraped"])
        log.info("Records found:    {}", self._stats["records_extracted"])
        log.info("Records saved:    {}", self._stats["records_saved"])
        log.info("Errors:           {}", self._stats["errors"])
        if self._csv:
            log.info("{}", self._csv.summary())
        log.info("=" * 60)

    # ─── Main Entry Point ────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run the full scraping pipeline."""
        await self.start()
        try:
            await self._scrape_all_pages()
        except asyncio.CancelledError:
            log.warning("Scraping interrupted by user")
        except Exception as exc:
            log.exception("Fatal error during scraping: {}", exc)
            raise
        finally:
            await self.stop()

    # ─── Pagination Loop ─────────────────────────────────────────────────────

    async def _scrape_all_pages(self) -> None:
        """Navigate and scrape all listing pages up to max_pages."""
        page = await self._browser.new_page()
        human = HumanSimulator(page)

        current_url = settings.target_url
        page_num = 1

        # Pre-load session cookies if available
        await self._browser.load_cookies()

        while current_url and page_num <= self._max_pages:
            log.info("─" * 50)
            log.info("Scraping page {}/{} | url={}", page_num, self._max_pages, current_url[:80])

            records = await self._scrape_page_with_retry(
                page=page,
                human=human,
                url=current_url,
                page_num=page_num,
            )

            if records:
                await self._save_records(records)
                self._stats["records_extracted"] += len(records)

            self._stats["pages_scraped"] += 1

            # Get next page URL
            next_url = await self._parser.get_next_page_url(page, page_num)

            if not next_url:
                log.info("No next page found — pagination complete")
                break

            current_url = next_url
            page_num += 1

            # Human-like inter-page delay
            await random_delay()

        await page.close()

    # ─── Single Page Scraping with Retry ─────────────────────────────────────

    async def _scrape_page_with_retry(
        self,
        page,
        human: HumanSimulator,
        url: str,
        page_num: int,
    ) -> list[PutusanRecord]:
        """
        Scrape a single page with automatic retry on failure.
        Uses exponential backoff (tenacity).
        """
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.max_retries),
                wait=wait_exponential(
                    multiplier=settings.retry_backoff_base,
                    min=2,
                    max=60,
                ),
                retry=retry_if_exception_type(Exception),
                reraise=False,
            ):
                with attempt:
                    attempt_num = attempt.retry_state.attempt_number
                    if attempt_num > 1:
                        log.warning(
                            "Retry {}/{} for page {}",
                            attempt_num,
                            settings.max_retries,
                            page_num,
                        )

                    return await self._load_and_extract(page, human, url, page_num)

        except RetryError:
            log.error("All retries exhausted for page {} | url={}", page_num, url)
            self._stats["errors"] += 1
            return []
        except Exception as exc:
            log.error("Unexpected error on page {}: {}", page_num, exc)
            self._stats["errors"] += 1
            return []

        return []

    async def _load_and_extract(
        self,
        page,
        human: HumanSimulator,
        url: str,
        page_num: int,
    ) -> list[PutusanRecord]:
        """Navigate to URL, wait for content, simulate human, extract records."""

        # Navigate
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=settings.browser_timeout,
        )

        if response and response.status >= 400:
            log.warning("HTTP {} on page {} | url={}", response.status, page_num, url)
            if response.status in (403, 429, 503):
                # Anti-bot response — wait longer before retry
                await asyncio.sleep(15)
                raise Exception(f"HTTP {response.status} — possible anti-bot block")

        # Wait for content to appear
        await self._wait_for_content(page)

        # Human simulation: random mouse moves + scroll
        await human.move_mouse_randomly(num_moves=random.randint(2, 5))
        await human.scroll_page_naturally()
        await human.move_mouse_randomly(num_moves=2)

        # Extract records
        records = await self._parser.extract_records(page, page_num)

        # Optionally visit detail pages for PDF links
        if records and not all(r.url_pdf for r in records):
            records = await self._enrich_with_details(page, records)

        return records

    async def _wait_for_content(self, page) -> None:
        """Wait until the page has rendered enough content."""
        try:
            # Wait for at minimum one anchor or table row
            await page.wait_for_selector(
                "table tr, .card, a[href*='putusan'], a[href*='detail']",
                timeout=15_000,
                state="attached",
            )
        except Exception:
            log.debug("Content wait selector timed out — proceeding anyway")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass

    # ─── Detail Page Enrichment ───────────────────────────────────────────────

    async def _enrich_with_details(
        self,
        page,
        records: list[PutusanRecord],
    ) -> list[PutusanRecord]:
        """
        Visit detail pages to fetch PDF links for records that are missing them.
        Limits to first 5 records per page to avoid excessive requests.
        """
        enriched_count = 0
        limit = min(5, len(records))

        for record in records[:limit]:
            if record.url_pdf or not record.url_detail:
                continue

            try:
                await page.goto(record.url_detail, wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(random.uniform(1.0, 2.5))
                detail = await self._parser.extract_detail(page)

                if detail.get("url_pdf"):
                    record.url_pdf = detail["url_pdf"]
                    enriched_count += 1

                # Merge extra metadata
                extra = detail.get("metadata", {})
                if extra:
                    record.metadata.extra.update(extra)

            except Exception as exc:
                log.debug("Detail page error for {}: {}", record.url_detail[:60], exc)

        if enriched_count:
            log.debug("Enriched {} records with PDF links", enriched_count)

        # Navigate back to listing
        try:
            await page.go_back(wait_until="domcontentloaded", timeout=10_000)
        except Exception:
            pass

        return records

    # ─── Persistence ─────────────────────────────────────────────────────────

    async def _save_records(self, records: list[PutusanRecord]) -> None:
        """Write records to all enabled output targets."""
        if not records:
            return

        saved = 0

        # Save to PostgreSQL
        if self._use_db:
            saved_db = await db.bulk_upsert(records)
            saved = max(saved, saved_db)

        # Save to CSV
        if self._use_csv and self._csv:
            saved_csv = await self._csv.write_records(records)
            saved = max(saved, saved_csv)

        self._stats["records_saved"] += saved


# ─── Import needed inside method ─────────────────────────────────────────────
import random
