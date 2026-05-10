"""
scraper/browser.py — Stealth Chromium Browser Manager

Menggunakan PERSISTENT browser context agar cookie Cloudflare cf_clearance
tetap tersimpan antar sesi. User cukup solve Turnstile sekali di jendela
Chromium yang muncul, lalu semua request berikutnya pakai cookie tersebut.

Perbaikan dari versi sebelumnya:
- headless default True (aman untuk Docker)
- Resource blocking tidak memblok halaman warm-up (CF butuh semua resource)
- Timeout handling lebih robust
- Browser args tambahan untuk Docker
"""

from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.config import CHROMIUM_ARGS, get_random_user_agent, settings
from app.utils.logger import log

# ─── Stealth JS Injection ─────────────────────────────────────────────────────
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined, configurable: true
});
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const p = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client',     filename: 'internal-nacl-plugin' },
        ];
        p.refresh = () => {};
        p.item    = (i) => p[i];
        p.namedItem = (n) => p.find(x => x.name === n);
        return p;
    }
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['id-ID', 'id', 'en-US', 'en'],
});
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(params);
window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: {} };
"""

# Persistent profile untuk simpan cookies cf_clearance
USER_DATA_DIR = Path(settings.data_dir) / "browser_profile"

# Resource types yang diblok saat scraping (BUKAN saat warmup)
BLOCKED_RESOURCES = {"image", "font", "media", "stylesheet"}


class StealthBrowser:
    """
    Stealth Playwright Chromium dengan persistent context.
    Cookie cf_clearance tersimpan otomatis dan bertahan antar restart.
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._user_agent: str = get_random_user_agent()
        self._ready = False
        self._warmup_status: str = "idle"
        self._warmup_page: Optional[Page] = None
        self._is_warmup_mode: bool = False  # flag untuk disable resource blocking

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def warmup_status(self) -> str:
        return self._warmup_status

    @warmup_status.setter
    def warmup_status(self, value: str) -> None:
        self._warmup_status = value

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch Chromium dengan stealth config dan persistent context."""
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Tambahkan args khusus Docker jika headless
        args = list(CHROMIUM_ARGS)
        if settings.headless:
            args += [
                "--disable-gpu",
                "--single-process",  # lebih stabil di Docker
            ]

        log.info(
            "Launching Chromium | headless={} | profile={} | ua={:.50s}…",
            settings.headless, USER_DATA_DIR, self._user_agent,
        )

        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=settings.headless,
            args=args,
            user_agent=self._user_agent,
            viewport={
                "width": random.randint(1280, 1920),
                "height": random.randint(768, 1080),
            },
            locale="id-ID",
            timezone_id="Asia/Jakarta",
            geolocation={"latitude": -6.2088, "longitude": 106.8456},
            permissions=["geolocation"],
            extra_http_headers={
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            timeout=settings.browser_timeout,
        )

        # Inject stealth script di setiap halaman baru
        await self._context.add_init_script(STEALTH_SCRIPT)

        # Resource blocking — skip jika sedang warmup (CF butuh semua resource)
        async def _route_handler(route):
            if self._is_warmup_mode:
                await route.continue_()
                return
            if route.request.resource_type in BLOCKED_RESOURCES:
                await route.abort()
            else:
                await route.continue_()

        await self._context.route("**/*", _route_handler)

        self._ready = True
        log.success("Stealth browser ready (persistent context)")

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._ready = False
        if self._warmup_page:
            try:
                await self._warmup_page.close()
            except Exception:
                pass
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        log.info("Browser closed")

    # ─── Page Management ──────────────────────────────────────────────────────

    async def new_page(self) -> Page:
        """Buat halaman baru dengan stealth."""
        if not self._context:
            raise RuntimeError("Browser belum distart — panggil start() dulu")
        page = await self._context.new_page()
        page.set_default_timeout(settings.browser_timeout)
        page.set_default_navigation_timeout(settings.browser_timeout)
        return page

    # ─── Warm-Up (Cloudflare Bypass) ─────────────────────────────────────────

    async def warmup(self) -> bool:
        """
        Buka halaman target di Chromium.
        Jika ada Cloudflare Turnstile, user solve manual di jendela yang muncul.
        Cookie disimpan otomatis via persistent context.
        """
        self._warmup_status = "warming"
        self._is_warmup_mode = True  # disable resource blocking saat warmup
        target = settings.direktori_url
        log.info("Warm-up: navigating to {}", target)

        try:
            if self._warmup_page:
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass

            self._warmup_page = await self.new_page()

            await self._warmup_page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )

            html = await self._warmup_page.content()
            if self._is_cloudflare_challenge(html):
                self._warmup_status = "challenge"
                log.warning(
                    "Cloudflare Turnstile terdeteksi! "
                    "Selesaikan verifikasi di jendela Chromium."
                )
                # Jangan tunggu — return, frontend akan poll /api/warmup-status
                return False
            else:
                self._warmup_status = "solved"
                self._is_warmup_mode = False
                log.success("Tidak ada challenge — akses langsung OK!")
                return True

        except Exception as exc:
            log.error("Warm-up error: {}", exc)
            self._warmup_status = "failed"
            self._is_warmup_mode = False
            return False

    async def check_warmup_solved(self) -> bool:
        """
        Cek apakah Cloudflare challenge sudah di-solve user.
        Dipanggil oleh frontend polling /api/warmup-status.
        """
        if self._warmup_status == "solved":
            return True
        if not self._warmup_page:
            return False

        try:
            html = await self._warmup_page.content()
            if not self._is_cloudflare_challenge(html):
                self._warmup_status = "solved"
                self._is_warmup_mode = False
                log.success("Challenge solved! Cookie cf_clearance tersimpan.")
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass
                self._warmup_page = None
                return True
        except Exception as exc:
            log.debug("Warmup check error: {}", exc)

        return False

    @staticmethod
    def _is_cloudflare_challenge(html: str) -> bool:
        lower = html.lower()
        return any(marker in lower for marker in [
            "cf-turnstile", "verify you are human", "just a moment",
            "checking your browser", "cf_chl_opt", "cf-challenge-running",
        ])

    # ─── Cookie Check ─────────────────────────────────────────────────────────

    async def has_cf_clearance(self) -> bool:
        """Cek apakah cookie cf_clearance sudah ada."""
        if not self._context:
            return False
        try:
            cookies = await self._context.cookies()
            return any(c["name"] == "cf_clearance" for c in cookies)
        except Exception:
            return False

    # ─── Human Simulation ─────────────────────────────────────────────────────

    async def human_scroll(self, page: Page, scrolls: int = 3) -> None:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        for _ in range(scrolls):
            amount = random.randint(
                int(vp["height"] * 0.3),
                int(vp["height"] * 0.8),
            )
            await page.evaluate(
                f"window.scrollBy({{top: {amount}, behavior: 'smooth'}})"
            )
            await asyncio.sleep(
                random.uniform(settings.scroll_delay_min, settings.scroll_delay_max)
            )

    async def random_mouse(self, page: Page, moves: int = 3) -> None:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        for _ in range(moves):
            x = random.randint(100, vp["width"] - 100)
            y = random.randint(100, vp["height"] - 100)
            await page.mouse.move(x, y, steps=random.randint(5, 15))
            await asyncio.sleep(random.uniform(0.05, 0.15))

    # ─── Context Manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "StealthBrowser":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


# ─── Singleton ────────────────────────────────────────────────────────────────
browser_manager = StealthBrowser()
