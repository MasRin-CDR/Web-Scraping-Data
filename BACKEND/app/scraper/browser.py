"""
scraper/browser.py — Production Stealth Chromium Browser Manager (v2)

Perbaikan dari v1:
- Integrasi penuh dengan utils/stealth.py (stealth script lebih lengkap)
- Cookie Manager integration (auto-load/save ke disk)
- Extra HTTP headers yang lebih realistis
- Screenshot support untuk debugging
- warmup_page tidak diclose langsung — tunggu user solve Turnstile
- Proper async lifecycle dengan asyncio.Lock
- headless=False default di development, True di production
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
from app.utils.stealth import (
    STEALTH_INIT_SCRIPT,
    apply_stealth_to_page,
    get_extra_http_headers,
    get_random_viewport,
    get_random_timezone,
)

# ─── Paths ────────────────────────────────────────────────────────────────────
# Persistent browser profile — simpan cookies termasuk cf_clearance
USER_DATA_DIR = Path(settings.data_dir) / "browser_profile"

# Resource types yang diblok saat scraping (BUKAN saat warmup — CF butuh semua)
BLOCKED_RESOURCES = {"image", "font", "media"}

# Jangan blok stylesheet — beberapa halaman CF membutuhkannya untuk rendering
# "stylesheet" dihapus dari BLOCKED_RESOURCES v2


class StealthBrowser:
    """
    Stealth Playwright Chromium dengan persistent context.

    Features v2:
    - Advanced stealth JS injection (12 evasion techniques)
    - Cookie cf_clearance tersimpan otomatis (browser profile + JSON disk)
    - Resource blocking adaptif (skip saat warmup)
    - Human simulation (mouse, scroll, delay)
    - Thread-safe via asyncio.Lock
    - Screenshot support
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._user_agent: str = get_random_user_agent()
        self._viewport: dict = get_random_viewport()
        self._timezone: str = get_random_timezone()
        self._ready = False
        self._warmup_status: str = "idle"
        self._warmup_page: Optional[Page] = None
        self._is_warmup_mode: bool = False
        self._start_lock = asyncio.Lock()

    # ─── Properties ───────────────────────────────────────────────────────────

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
        """
        Launch Chromium dengan stealth config dan persistent context.
        Thread-safe via asyncio.Lock — hanya satu instance yang berjalan.
        """
        async with self._start_lock:
            if self._ready:
                if await self._context_is_alive():
                    log.debug("Browser sudah running - skip start()")
                    return
                log.warning("Browser flag ready, but context is closed; restarting Chromium")
                await self._reset_handles()
            if False:
                log.debug("Browser sudah running — skip start()")
                return

            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

            # Build Chromium args
            args = list(CHROMIUM_ARGS)
            if settings.headless:
                args += [
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    # "--single-process",  # matikan — lebih stabil multi-process
                ]

            log.info(
                "🚀 Launching Chromium | headless={} | UA={:.60s}… | viewport={}x{}",
                settings.headless,
                self._user_agent,
                self._viewport["width"],
                self._viewport["height"],
            )

            self._playwright = await async_playwright().start()

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=settings.headless,
                args=args,
                user_agent=self._user_agent,
                viewport=self._viewport,
                locale="id-ID",
                timezone_id=self._timezone,
                geolocation={"latitude": -6.2088, "longitude": 106.8456},
                permissions=["geolocation"],
                extra_http_headers=get_extra_http_headers(self._user_agent),
                accept_downloads=True,
                timeout=settings.browser_timeout,
                ignore_https_errors=True,
                # Java disabled untuk reduce fingerprint surface
                java_script_enabled=True,
            )

            # ── Inject stealth init script ke SEMUA halaman baru ──────────────
            await self._context.add_init_script(STEALTH_INIT_SCRIPT)

            executable_path = getattr(self._playwright.chromium, "executable_path", None)
            browser = self._context.browser
            browser_version = (
                await browser.version()
                if browser is not None
                else "<persistent-context>"
            )
            log.info("Chromium executable path: {}", executable_path or "<unavailable>")
            log.info("Chromium browser version: {}", browser_version)

            # ── Adaptive resource blocking ─────────────────────────────────────
            async def _route_handler(route):
                if self._is_warmup_mode:
                    # Saat warmup: izinkan SEMUA resource (CF butuh JS, CSS, dll)
                    await route.continue_()
                    return
                req_type = route.request.resource_type
                if req_type in BLOCKED_RESOURCES:
                    await route.abort()
                else:
                    await route.continue_()

            await self._context.route("**/*", _route_handler)

            self._ready = True
            log.success(
                "✅ Stealth browser ready | persistent profile: {} | timezone: {}",
                USER_DATA_DIR,
                self._timezone,
            )

    async def stop(self) -> None:
        """Graceful shutdown — tutup warmup page, context, dan playwright."""
        self._ready = False

        # Tutup warmup page jika masih terbuka
        if self._warmup_page:
            try:
                await self._warmup_page.close()
            except Exception:
                pass
            self._warmup_page = None

        # Tutup context (otomatis menyimpan cookies ke persistent profile)
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        # Stop playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        log.info("🛑 Browser closed")

    # ─── Page Management ──────────────────────────────────────────────────────

    async def _context_is_alive(self) -> bool:
        """Best-effort check for a still-open Playwright context."""
        if not self._context:
            return False
        try:
            await self._context.cookies()
            return True
        except Exception:
            return False

    async def _reset_handles(self) -> None:
        """Clear stale Playwright handles after an unexpected browser close."""
        self._ready = False
        self._warmup_page = None
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._playwright = None

    async def new_page(self) -> Page:
        """Buat halaman baru dengan timeout dan stealth sudah terkonfigurasi."""
        if self._context and not await self._context_is_alive():
            await self._reset_handles()
        if not self._context:
            await self.start()
        if not self._context:
            raise RuntimeError("Browser belum distart — panggil start() dulu")
        try:
            page = await self._context.new_page()
        except Exception as exc:
            if "Target page, context or browser has been closed" not in str(exc):
                raise
            log.warning("Browser context closed while opening page; restarting Chromium")
            await self._reset_handles()
            await self.start()
            if not self._context:
                raise RuntimeError("Browser restart gagal")
            page = await self._context.new_page()
        page.set_default_timeout(settings.browser_timeout)
        page.set_default_navigation_timeout(settings.browser_timeout)
        return page

    # ─── Warmup (Cloudflare Bypass) ───────────────────────────────────────────

    async def warmup(self) -> bool:
        """
        Buka halaman target di Chromium.

        Jika ada Cloudflare Turnstile:
        - headless=False: jendela muncul, user solve manual
        - headless=True: tunggu auto-solve (biasanya gagal, perlu unblock dulu)

        Cookie disimpan otomatis via persistent context (browser profile).
        Cookie JUGA di-sync ke cookies/session.json oleh BrowserManagerService.

        Return True jika akses langsung OK (tidak ada challenge).
        Return False jika challenge terdeteksi (poll /api/warmup-status).
        """
        self._warmup_status = "warming"
        self._is_warmup_mode = True  # disable resource blocking

        target = settings.direktori_url
        log.info("🔥 Warmup: navigating to {}", target)

        try:
            # Tutup warmup page sebelumnya jika ada
            if self._warmup_page:
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass

            self._warmup_page = await self.new_page()

            # Inject stealth post-load ke warmup page
            await apply_stealth_to_page(self._warmup_page)

            # Navigate ke target
            response = await self._warmup_page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )

            # Log HTTP status
            if response:
                log.info(
                    "Warmup page response: HTTP {} | url={}",
                    response.status,
                    response.url,
                )

            # Tunggu sebentar untuk JS load
            await asyncio.sleep(2.0)

            html = await self._warmup_page.content()

            if self._is_cloudflare_challenge(html):
                self._warmup_status = "challenge"
                log.warning(
                    "⚠️ Cloudflare Turnstile terdeteksi! "
                    "{}",
                    (
                        "Selesaikan verifikasi di jendela Chromium."
                        if not settings.headless
                        else "Mode headless=True: tidak bisa auto-solve. "
                             "Set headless=False untuk manual solve."
                    ),
                )
                return False
            else:
                # Akses berhasil tanpa challenge
                self._warmup_status = "solved"
                self._is_warmup_mode = False
                log.success("✅ Warmup: akses langsung berhasil — tidak ada challenge!")

                # Tutup warmup page karena tidak diperlukan lagi
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass
                self._warmup_page = None

                return True

        except asyncio.TimeoutError:
            log.error("Warmup timeout — halaman tidak merespons dalam waktu {:.0f}ms",
                      settings.browser_timeout)
            self._warmup_status = "failed"
            self._is_warmup_mode = False
            return False
        except Exception as exc:
            log.error("Warmup error: {}", exc)
            self._warmup_status = "failed"
            self._is_warmup_mode = False
            return False

    async def check_warmup_solved(self) -> bool:
        """
        Cek apakah Cloudflare challenge sudah diselesaikan user.
        Dipanggil saat polling GET /api/warmup-status.

        Return True jika challenge sudah selesai (cookie cf_clearance ada).
        """
        if self._warmup_status == "solved":
            return True

        if not self._warmup_page:
            # Jika warmup_page sudah ditutup tapi status masih challenge
            # → cek dari cookies
            has_cf = await self.has_cf_clearance()
            if has_cf:
                self._warmup_status = "solved"
                return True
            return False

        try:
            # Cek konten halaman warmup
            html = await self._warmup_page.content()

            if not self._is_cloudflare_challenge(html):
                # Challenge solved!
                self._warmup_status = "solved"
                self._is_warmup_mode = False

                log.success(
                    "✅ Cloudflare challenge diselesaikan! Cookie cf_clearance tersimpan."
                )

                # Tunggu sebentar agar cookie cf_clearance benar-benar set
                await asyncio.sleep(1.5)

                # Tutup warmup page
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass
                self._warmup_page = None

                return True

        except Exception as exc:
            log.debug("Warmup check error (mungkin page sudah tutup): {}", exc)

            # Jika page sudah tutup, cek dari cookies
            has_cf = await self.has_cf_clearance()
            if has_cf:
                self._warmup_status = "solved"
                self._warmup_page = None
                return True

        return False

    # ─── Challenge Detection ──────────────────────────────────────────────────

    @staticmethod
    def _is_cloudflare_challenge(html: str) -> bool:
        """Deteksi Cloudflare challenge dari HTML content."""
        if not html or len(html) < 100:
            return True  # Halaman kosong = mencurigakan
        lower = html.lower()
        markers = (
            "cf-turnstile",
            "verify you are human",
            "just a moment",
            "checking your browser",
            "cf_chl_opt",
            "cf-challenge-running",
            "challenge-platform",
            "turnstile.cloudflare.com",
            "_cf_chl_f_tk",
        )
        return any(m in lower for m in markers)

    # ─── Cookie Operations ────────────────────────────────────────────────────

    async def has_cf_clearance(self) -> bool:
        """Cek apakah cookie cf_clearance ada di browser context."""
        if not self._context:
            return False
        try:
            cookies = await self._context.cookies()
            return any(c["name"] == "cf_clearance" for c in cookies)
        except Exception:
            return False

    async def get_all_cookies(self) -> list:
        """Return semua cookies dari browser context."""
        if not self._context:
            return []
        try:
            return await self._context.cookies()
        except Exception:
            return []

    # ─── Human Simulation ─────────────────────────────────────────────────────

    async def human_scroll(self, page: Page, scrolls: int = 3) -> None:
        """Simulasi scroll manusia — gerak halus dengan jeda acak."""
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
        """Simulasi pergerakan mouse acak yang realistis."""
        vp = page.viewport_size or {"width": 1280, "height": 800}
        # Mulai dari posisi tengah
        cx, cy = vp["width"] // 2, vp["height"] // 2
        for _ in range(moves):
            # Bergerak sedikit-sedikit (bukan langsung ke tujuan)
            tx = random.randint(100, vp["width"] - 100)
            ty = random.randint(100, vp["height"] - 100)
            # Intermediate steps untuk gerakan lebih realistis
            mid_x = (cx + tx) // 2 + random.randint(-30, 30)
            mid_y = (cy + ty) // 2 + random.randint(-30, 30)
            await page.mouse.move(mid_x, mid_y, steps=random.randint(5, 10))
            await asyncio.sleep(random.uniform(0.03, 0.1))
            await page.mouse.move(tx, ty, steps=random.randint(5, 15))
            await asyncio.sleep(random.uniform(0.05, 0.2))
            cx, cy = tx, ty

    async def take_screenshot(self, page: Page, path: str) -> Optional[str]:
        """Ambil screenshot halaman. Return path jika berhasil."""
        try:
            from pathlib import Path as P
            P(path).parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=path, full_page=False)
            log.debug("📸 Screenshot: {}", path)
            return path
        except Exception as exc:
            log.debug("Screenshot gagal: {}", exc)
            return None

    # ─── Context Manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "StealthBrowser":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()


# ─── Singleton ────────────────────────────────────────────────────────────────
browser_manager = StealthBrowser()
