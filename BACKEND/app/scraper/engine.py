"""
scraper/engine.py — Scraping Engine
Orchestrates browser navigation, page loading, retry logic,
and data extraction for search and detail pages.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any, Dict, List, Optional

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.scraper.browser import StealthBrowser, browser_manager
from app.scraper.parser import PageParser, parser
from app.utils.helpers import (
    build_search_url,
    normalize_url,
    random_delay,
)
from app.utils.logger import log


class ScrapingEngine:
    """
    High-level scraping engine.
    - search(): scrape search/directory results across pages
    - get_detail(): scrape a single putusan detail page
    - download_pdf(): fetch a PDF and return its bytes
    """

    def __init__(
        self,
        browser: Optional[StealthBrowser] = None,
        page_parser: Optional[PageParser] = None,
    ) -> None:
        self._browser = browser or browser_manager
        self._parser = page_parser or parser

    # ─── Search Scraping ──────────────────────────────────────────────────────

    async def search(
        self,
        keyword: str = "",
        lokasi: str = "",
        jenis: str = "",
        max_pages: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Scrape search results from putusan3.mahkamahagung.go.id.
        Returns a flat list of putusan dicts across all scraped pages.
        Requires warm-up (cf_clearance cookie) to be done first.
        """
        if max_pages <= 0:
            max_pages = settings.max_pages_per_search

        if not self._browser.is_ready:
            log.warning("Browser not ready — starting now")
            await self._browser.start()

        # Check if Cloudflare cookies exist
        has_cf = await self._browser.has_cf_clearance()
        if not has_cf:
            log.warning(
                "No cf_clearance cookie — search may fail. "
                "Run /api/warmup first to solve the Cloudflare challenge."
            )

        page = await self._browser.new_page()
        all_records: List[Dict] = []

        try:
            page_num = 1
            current_url = build_search_url(
                settings.target_base_url, keyword, lokasi, jenis, page_num
            )

            while current_url and page_num <= max_pages:
                log.info(
                    "Scraping page {}/{} | url={:.80s}",
                    page_num, max_pages, current_url,
                )

                records = await self._scrape_single_page(
                    page, current_url, page_num
                )

                if records:
                    # Enrich with lokasi/jenis filters if provided
                    for rec in records:
                        if lokasi and not rec.get("lokasi"):
                            rec["lokasi"] = lokasi
                        if jenis and not rec.get("jenis_peradilan"):
                            rec["jenis_peradilan"] = jenis
                    all_records.extend(records)

                # Get next page URL
                html = await page.content()
                next_url = self._parser.parse_next_page_url(html, page_num)

                if not next_url:
                    log.info("No next page — pagination complete at page {}", page_num)
                    break

                current_url = next_url
                page_num += 1
                await random_delay()

        except asyncio.CancelledError:
            log.warning("Search scraping cancelled")
        except Exception as exc:
            log.error("Search scraping error: {}", exc)
        finally:
            await page.close()

        log.info("Search complete | total records: {}", len(all_records))
        return all_records

    # ─── Single Page with Retry ───────────────────────────────────────────────

    async def _scrape_single_page(
        self,
        page,
        url: str,
        page_num: int,
    ) -> List[Dict]:
        """Scrape one page with automatic retry + exponential backoff."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.max_retries),
                wait=wait_exponential(multiplier=2, min=3, max=30),
                retry=retry_if_exception_type(Exception),
                reraise=False,
            ):
                with attempt:
                    attempt_num = attempt.retry_state.attempt_number
                    if attempt_num > 1:
                        log.warning(
                            "Retry {}/{} for page {}",
                            attempt_num, settings.max_retries, page_num,
                        )
                    return await self._navigate_and_extract(page, url, page_num)

        except RetryError:
            log.error("All retries exhausted for page {} | url={:.60s}", page_num, url)
            return []
        except Exception as exc:
            log.error("Unexpected error on page {}: {}", page_num, exc)
            return []
        return []

    async def _navigate_and_extract(
        self, page, url: str, page_num: int
    ) -> List[Dict]:
        """Navigate to URL, wait for content, simulate human, extract."""
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=settings.browser_timeout,
        )

        if response and response.status >= 400:
            log.warning("HTTP {} on page {}", response.status, page_num)

            # Check for Cloudflare challenge
            html = await page.content()
            if self._browser._is_cloudflare_challenge(html):
                raise Exception(
                    f"HTTP {response.status} — Cloudflare challenge. "
                    f"Run warm-up first via /api/warmup"
                )

            if response.status in (403, 429, 503):
                await asyncio.sleep(10)
                raise Exception(f"HTTP {response.status} — rate limit or block")

        # Wait for content
        await self._wait_for_content(page)

        # Human simulation
        await self._browser.random_mouse(page, moves=random.randint(2, 4))
        await self._browser.human_scroll(page, scrolls=random.randint(2, 4))

        # Extract HTML and parse with BeautifulSoup
        html = await page.content()
        records = self._parser.parse_search_results(html, page_num)

        log.info("Page {} | extracted {} records", page_num, len(records))
        return records

    async def _wait_for_content(self, page) -> None:
        """Wait until meaningful content is visible."""
        try:
            await page.wait_for_selector(
                "table tr, .card, a[href*='putusan'], a[href*='detail'], "
                ".search-result, .skel-result, #popular_keyword, "
                ".direktori, #direktoriMenu",
                timeout=15_000,
                state="attached",
            )
        except Exception:
            log.debug("Content selector timed out — proceeding anyway")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass

    # ─── Detail Page ──────────────────────────────────────────────────────────

    async def get_detail(self, detail_url: str) -> Dict[str, Any]:
        """Scrape a single putusan detail page."""
        if not self._browser.is_ready:
            await self._browser.start()

        page = await self._browser.new_page()
        try:
            response = await page.goto(
                detail_url,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )

            if response and response.status >= 400:
                log.warning("HTTP {} on detail page", response.status)
                html = await page.content()
                if self._browser._is_cloudflare_challenge(html):
                    return {
                        "url_detail": detail_url,
                        "error": "Cloudflare challenge — run warm-up first",
                    }
                if response.status in (403, 429, 503):
                    await asyncio.sleep(10)

            await self._wait_for_content(page)
            await self._browser.human_scroll(page, scrolls=2)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            html = await page.content()
            detail = self._parser.parse_detail_page(html)
            detail["url_detail"] = detail_url
            return detail

        except Exception as exc:
            log.error("Detail scraping error for {:.60s}: {}", detail_url, exc)
            return {"url_detail": detail_url, "error": str(exc)}
        finally:
            await page.close()

    # ─── PDF Download ─────────────────────────────────────────────────────────

    async def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """Download a PDF file via the browser context. Returns raw bytes."""
        if not self._browser.is_ready:
            await self._browser.start()

        page = await self._browser.new_page()
        try:
            response = await page.goto(
                pdf_url,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )
            if response:
                body = await response.body()
                return body
        except Exception as exc:
            log.error("PDF download error for {:.60s}: {}", pdf_url, exc)
        finally:
            await page.close()
        return None


# ─── Singleton ────────────────────────────────────────────────────────────────
scraping_engine = ScrapingEngine()
