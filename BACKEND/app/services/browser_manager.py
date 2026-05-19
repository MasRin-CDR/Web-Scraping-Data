"""
services/browser_manager.py — Production Browser Manager Service

Layer SERVICE di atas scraper/browser.py:
- Koordinasi warmup + cookie sync
- Auto-load cookie saat startup
- Validasi session
- Browser status reporting
- Screenshot management
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings
from app.services.cloudflare_service import CloudflareService, cloudflare_service
from app.services.cookie_manager import cookie_manager
from app.utils.logger import log

# Dir untuk menyimpan screenshot challenge
SCREENSHOTS_DIR = Path(settings.data_dir) / "screenshots"


class BrowserManagerService:
    """
    High-level service yang mengorkestrasi:
    1. Browser lifecycle (start/stop)
    2. Warmup Cloudflare dengan cookie persistence
    3. Cookie auto-load saat startup
    4. Session validation
    5. Status reporting untuk API
    """

    def __init__(self) -> None:
        self._started_at: Optional[datetime] = None
        self._last_warmup: Optional[datetime] = None
        self._warmup_attempts: int = 0
        self._last_screenshot: Optional[str] = None
        self._lock = asyncio.Lock()  # agar concurrent warmup tidak overlap

    # ─── Startup / Init ───────────────────────────────────────────────────────

    async def initialize(self) -> Dict[str, Any]:
        """
        Panggil ini saat FastAPI startup.
        1. Launch browser
        2. Load cookies dari disk
        3. Apply cookies ke browser context
        4. Validasi session
        Returns status dict.
        """
        # Import di sini untuk hindari circular import
        from app.scraper.browser import browser_manager as bm

        result = {
            "browser_started": False,
            "cookies_loaded": False,
            "cf_clearance": False,
            "session_valid": False,
            "needs_warmup": True,
        }

        # 1. Launch browser
        try:
            if not bm.is_ready:
                await bm.start()
            self._started_at = datetime.now(tz=timezone.utc)
            result["browser_started"] = True
            log.success("Browser Manager: browser started")
        except Exception as exc:
            log.error("Browser Manager: browser gagal start: {}", exc)
            return result

        # 2. Load cookies dari disk
        cookies = await cookie_manager.load()
        if cookies:
            result["cookies_loaded"] = True

        # 3. Apply cookies ke browser context (agar cf_clearance aktif)
        if cookies and bm._context:
            has_cf = await cookie_manager.apply_to_context(bm._context)
            result["cf_clearance"] = has_cf
            if has_cf:
                bm.warmup_status = "solved"
                result["session_valid"] = True
                result["needs_warmup"] = False
                log.success("Session Cloudflare valid — warmup tidak diperlukan")
            else:
                log.warning("cf_clearance tidak ditemukan — warmup diperlukan")
        else:
            log.warning("Tidak ada cookie — warmup diperlukan")

        return result

    # ─── Warmup ───────────────────────────────────────────────────────────────

    async def start_warmup(self) -> Dict[str, Any]:
        """
        Mulai proses warmup Cloudflare.
        Thread-safe via asyncio.Lock agar tidak ada 2 warmup bersamaan.

        Returns:
          status: "ok" | "challenge" | "failed" | "already_ok"
        """
        from app.scraper.browser import browser_manager as bm

        async with self._lock:
            self._warmup_attempts += 1
            log.info("Warmup #{} dimulai", self._warmup_attempts)

            # Sudah OK?
            if await bm.has_cf_clearance() and bm.warmup_status == "solved":
                if not cookie_manager.needs_refresh():
                    log.info("Session masih valid — warmup tidak diperlukan")
                    return {
                        "status": "already_ok",
                        "success": True,
                        "message": "Session Cloudflare masih valid, siap untuk pencarian.",
                        "cf_clearance": True,
                        "attempt": self._warmup_attempts,
                    }

            # Pastikan browser ready
            if not bm.is_ready:
                try:
                    await bm.start()
                except Exception as exc:
                    return {
                        "status": "failed",
                        "success": False,
                        "message": f"Gagal start browser: {exc}",
                        "cf_clearance": False,
                        "attempt": self._warmup_attempts,
                    }

            # Lakukan warmup
            direct_access = await bm.warmup()

            status = bm.warmup_status  # "solved" | "challenge" | "failed"

            # Jika berhasil langsung (tidak ada challenge) → sync cookie
            if direct_access and status == "solved":
                await self._sync_cookies_after_warmup(bm)
                self._last_warmup = datetime.now(tz=timezone.utc)

            # Jika challenge muncul → ambil screenshot untuk debugging
            if status == "challenge" and bm._warmup_page:
                self._last_screenshot = await cloudflare_service.screenshot_challenge(
                    bm._warmup_page, SCREENSHOTS_DIR
                )

            return {
                "status": status,
                "success": status == "solved",
                "message": self._warmup_message(status),
                "cf_clearance": await bm.has_cf_clearance(),
                "screenshot": self._last_screenshot if status == "challenge" else None,
                "attempt": self._warmup_attempts,
            }

    async def check_warmup_status(self) -> Dict[str, Any]:
        """
        Poll status warmup — dipanggil frontend setiap beberapa detik.
        Jika challenge sudah selesai, sync cookie ke disk.
        """
        from app.scraper.browser import browser_manager as bm

        status = bm.warmup_status

        # Cek apakah challenge sudah di-solve user
        if status == "challenge":
            solved = await bm.check_warmup_solved()
            if solved:
                status = "solved"
                await self._sync_cookies_after_warmup(bm)
                self._last_warmup = datetime.now(tz=timezone.utc)

        has_cf = await bm.has_cf_clearance()
        cookie_status = cookie_manager.status_dict()

        return {
            "status": status,
            "success": status == "solved",
            "message": self._warmup_message(status),
            "cf_clearance": has_cf,
            "cookie_info": cookie_status,
            "last_warmup": self._last_warmup.isoformat() if self._last_warmup else None,
            "warmup_attempts": self._warmup_attempts,
        }

    # ─── Session Validation ────────────────────────────────────────────────────

    async def is_session_valid(self) -> bool:
        """
        Cek apakah session Cloudflare masih valid.
        Cek dari browser context DAN dari cookie file.
        """
        from app.scraper.browser import browser_manager as bm

        # Cek dari browser context (paling akurat)
        if bm.is_ready:
            has_cf = await bm.has_cf_clearance()
            if has_cf:
                return True

        # Fallback: cek dari cookie file
        return cookie_manager.has_cf_clearance()

    # ─── Status untuk API ─────────────────────────────────────────────────────

    async def get_browser_status(self) -> Dict[str, Any]:
        """
        Return status lengkap browser + session untuk endpoint /api/browser-status.
        """
        from app.scraper.browser import browser_manager as bm

        has_cf = await bm.has_cf_clearance()
        cookie_status = cookie_manager.status_dict()

        # Hitung jumlah tab yang terbuka (pages)
        page_count = 0
        if bm._context:
            try:
                page_count = len(bm._context.pages)
            except Exception:
                pass

        return {
            "browser_ready": bm.is_ready,
            "warmup_status": bm.warmup_status,
            "cf_clearance_in_browser": has_cf,
            "session_valid": has_cf,
            "needs_warmup": not has_cf or cookie_manager.needs_refresh(),
            "headless": settings.headless,
            "open_pages": page_count,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_warmup": self._last_warmup.isoformat() if self._last_warmup else None,
            "warmup_attempts": self._warmup_attempts,
            "last_screenshot": self._last_screenshot,
            "cookie": cookie_status,
            "target_url": settings.direktori_url,
        }

    # ─── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _sync_cookies_after_warmup(bm) -> None:
        """Sync cookies dari browser context ke disk setelah warmup berhasil."""
        if bm._context:
            await cookie_manager.sync_from_context(bm._context)

    @staticmethod
    def _warmup_message(status: str) -> str:
        messages = {
            "idle":       "Warmup belum dimulai. Panggil POST /api/warmup untuk mulai.",
            "warming":    "Sedang membuka halaman target Cloudflare...",
            "challenge":  (
                "⚠️ Cloudflare Turnstile terdeteksi! "
                "Jika headless=False, selesaikan verifikasi di jendela Chromium. "
                "Poll GET /api/warmup-status sampai status 'solved'."
            ),
            "solved":     "✅ Cloudflare bypass berhasil! Session siap digunakan.",
            "failed":     "❌ Warmup gagal. Coba lagi dengan POST /api/warmup.",
            "already_ok": "✅ Session masih valid, tidak perlu warmup ulang.",
        }
        return messages.get(status, f"Status tidak dikenal: {status}")


# ─── Singleton ────────────────────────────────────────────────────────────────
browser_manager_service = BrowserManagerService()
