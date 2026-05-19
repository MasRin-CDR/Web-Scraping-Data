"""
services/scraper_service.py — Async Scraper Service (High-Level)

Wrapper service yang mengorkestrasi:
- Auto-retry dengan exponential backoff
- CF challenge detection selama scraping
- Screenshot saat error
- Humanlike delay antara request
- Thread-safe scraping via asyncio.Semaphore
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
from app.scraper.browser import browser_manager as bm
from app.scraper.engine import scraping_engine
from app.services.cloudflare_service import cloudflare_service, CloudflareService
from app.services.cookie_manager import cookie_manager
from app.utils.logger import log

# Maksimal request paralel (hati-hati — terlalu banyak bisa trigger CF)
_SCRAPE_SEMAPHORE = asyncio.Semaphore(2)

# Delay manusiawi antar request (detik)
HUMAN_DELAY_MIN = 2.0
HUMAN_DELAY_MAX = 5.0


class ScraperService:
    """
    Production-ready async scraping service dengan:
    - CF challenge guard
    - Auto retry
    - Human-like delays
    - Semaphore untuk rate limiting
    - Cookie refresh jika expired
    """

    # ─── Search ───────────────────────────────────────────────────────────────

    async def search(
        self,
        keyword: str = "",
        lokasi: str = "",
        jenis: str = "",
        max_pages: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Scrape hasil pencarian dengan retry + CF guard.
        Hanya berjalan jika session valid.
        """
        async with _SCRAPE_SEMAPHORE:
            # Validasi session sebelum scraping
            cf_ok = await self._ensure_session()
            if not cf_ok:
                log.warning("Scraper: session tidak valid, melanjutkan tanpa cf_clearance")

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
                                "🔄 Retry scraping #{} (max {})",
                                attempt_num, settings.max_retries,
                            )
                            # Delay lebih lama pada retry
                            await asyncio.sleep(random.uniform(5, 15))

                        records = await scraping_engine.search(
                            keyword=keyword,
                            lokasi=lokasi,
                            jenis=jenis,
                            max_pages=max_pages,
                        )

                        # Cek apakah hasil kosong karena CF (bukan karena tidak ada data)
                        if not records and attempt_num < settings.max_retries:
                            log.warning("Hasil kosong — mungkin CF challenge, akan retry")
                            raise Exception("Empty result — possible CF block")

                        return records

            except RetryError:
                log.error("Semua retry habis untuk search keyword='{}'", keyword)
                return []
            except Exception as exc:
                log.error("ScraperService.search error: {}", exc)
                return []

        return []

    # ─── Detail ───────────────────────────────────────────────────────────────

    async def get_detail(self, url: str) -> Dict[str, Any]:
        """
        Scrape detail page dengan retry dan CF guard.
        """
        async with _SCRAPE_SEMAPHORE:
            await self._ensure_session()
            await self._human_delay()

            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(settings.max_retries),
                    wait=wait_exponential(multiplier=2, min=3, max=20),
                    retry=retry_if_exception_type(Exception),
                    reraise=False,
                ):
                    with attempt:
                        attempt_num = attempt.retry_state.attempt_number
                        if attempt_num > 1:
                            log.warning("🔄 Retry detail #{}", attempt_num)
                            await asyncio.sleep(random.uniform(5, 12))

                        result = await scraping_engine.get_detail(url)

                        # Jika error karena CF, jangan retry (tidak akan berhasil tanpa warmup)
                        if result.get("error") and "cloudflare" in str(result["error"]).lower():
                            log.error("CF challenge pada detail page — stop retry")
                            return result

                        return result

            except RetryError:
                log.error("Semua retry habis untuk detail url={:.60s}", url)
                return {"url_detail": url, "error": "Max retries exceeded"}
            except Exception as exc:
                log.error("ScraperService.get_detail error: {}", exc)
                return {"url_detail": url, "error": str(exc)}

        return {"url_detail": url, "error": "Semaphore timeout"}

    # ─── PDF ──────────────────────────────────────────────────────────────────

    async def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """Download PDF dengan CF-authenticated browser context."""
        await self._ensure_session()
        return await scraping_engine.download_pdf(pdf_url)

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    @staticmethod
    async def _ensure_session() -> bool:
        """
        Pastikan browser ready dan session CF valid.
        Return True jika cf_clearance ada.
        """
        if not bm.is_ready:
            try:
                log.info("ScraperService: browser belum siap — mencoba start")
                await bm.start()
                # Load + apply cookies setelah start
                if bm._context:
                    await cookie_manager.apply_to_context(bm._context)
            except Exception as exc:
                log.error("ScraperService: gagal start browser: {}", exc)
                return False

        has_cf = await bm.has_cf_clearance()

        if not has_cf:
            # Coba apply cookie dari disk
            if cookie_manager.has_cf_clearance() and bm._context:
                applied = await cookie_manager.apply_to_context(bm._context)
                if applied:
                    log.info("ScraperService: cookie dari disk berhasil diterapkan")
                    return True
            log.warning("ScraperService: tidak ada cf_clearance — scraping mungkin gagal")

        return has_cf

    @staticmethod
    async def _human_delay() -> None:
        """Delay manusiawi antar request."""
        delay = random.uniform(HUMAN_DELAY_MIN, HUMAN_DELAY_MAX)
        log.debug("Human delay: {:.1f}s", delay)
        await asyncio.sleep(delay)


# ─── Singleton ────────────────────────────────────────────────────────────────
scraper_service = ScraperService()
