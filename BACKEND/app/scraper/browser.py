"""
scraper/browser.py — Stealth Chromium Browser Manager
Uses a PERSISTENT browser context so Cloudflare cf_clearance cookies
survive across sessions. The user solves the Turnstile challenge once
in the visible Chromium window, and all subsequent requests reuse
those cookies automatically.
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from app.config import CHROMIUM_ARGS, settings, get_random_user_agent
from app.utils.logger import log

# ─── Stealth JS Injection ─────────────────────────────────────────────────────
STEALTH_SCRIPT = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined, configurable: true
});

// Fake plugins array
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

// Override languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['id-ID', 'id', 'en-US', 'en'],
});

// Override permissions query
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(params);

// Chrome object
window.chrome = {
    runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: {},
};

// Fix iframe navigator.webdriver
const _iframeDesc = Object.getOwnPropertyDescriptor(
    HTMLIFrameElement.prototype, 'contentWindow'
);
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function () {
        const win = _iframeDesc.get.call(this);
        try {
            Object.defineProperty(win.navigator, 'webdriver', {
                get: () => undefined,
            });
        } catch (_) {}
        return win;
    },
});

// Randomize canvas fingerprint (very subtle)
const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
    const data = _origGetImageData.call(this, x, y, w, h);
    for (let i = 0; i < data.data.length; i += 4) {
        data.data[i]     += Math.floor(Math.random() * 3) - 1;
        data.data[i + 1] += Math.floor(Math.random() * 3) - 1;
        data.data[i + 2] += Math.floor(Math.random() * 3) - 1;
    }
    return data;
};
"""

# Persistent user data directory — stores cookies, localStorage, etc.
USER_DATA_DIR = Path(settings.data_dir) / "browser_profile"


class StealthBrowser:
    """
    Manages a single stealth Playwright Chromium instance with
    PERSISTENT browser context (user data directory).

    Features:
    - Anti-detection JS injection
    - Persistent cookie storage (cf_clearance survives restarts)
    - Randomized viewport & user-agent
    - Resource blocking (images/fonts) for speed
    - Human-like interactions
    - Warm-up status tracking
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._user_agent: str = get_random_user_agent()
        self._ready = False

        # Warm-up state (tracked for the frontend)
        self._warmup_status: str = "idle"  # idle | warming | challenge | solved | failed
        self._warmup_page: Optional[Page] = None

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
        """Launch Chromium with stealth configuration and persistent context."""
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        log.info(
            "Launching Chromium | headless={} | profile={} | ua={:.50s}…",
            settings.headless, USER_DATA_DIR, self._user_agent,
        )
        self._playwright = await async_playwright().start()

        # Use launchPersistentContext for cookie persistence
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=settings.headless,
            args=CHROMIUM_ARGS,
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
            # Increase default timeouts
            timeout=settings.browser_timeout,
        )

        # Inject stealth on every new page
        await self._context.add_init_script(STEALTH_SCRIPT)

        # Block heavy resources for speed (but NOT on warm-up pages)
        await self._context.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,otf,ico}",
            lambda route: route.abort(),
        )

        self._ready = True
        log.success("Stealth browser ready (persistent context)")

    async def stop(self) -> None:
        """Gracefully close everything."""
        if self._warmup_page:
            try:
                await self._warmup_page.close()
            except Exception:
                pass
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        self._ready = False
        log.info("Browser closed")

    # ─── Page Management ──────────────────────────────────────────────────────

    async def new_page(self) -> Page:
        """Create a new stealth page."""
        if not self._context:
            raise RuntimeError("Browser not started — call start() first")
        page = await self._context.new_page()
        page.set_default_timeout(settings.browser_timeout)
        page.set_default_navigation_timeout(settings.browser_timeout)
        return page

    # ─── Warm-Up (Cloudflare) ─────────────────────────────────────────────────

    async def warmup(self) -> bool:
        """
        Navigate to the target site homepage in a visible browser tab.
        If Cloudflare Turnstile appears, the user manually solves it.
        Cookies are persisted automatically via the persistent context.
        Returns True when the challenge is solved or no challenge exists.
        """
        self._warmup_status = "warming"
        target = settings.direktori_url
        log.info("Warm-up: navigating to {}", target)

        try:
            # Close existing warm-up page if any
            if self._warmup_page:
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass

            self._warmup_page = await self.new_page()

            response = await self._warmup_page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )

            # Check for Cloudflare challenge
            html = await self._warmup_page.content()
            if self._is_cloudflare_challenge(html):
                self._warmup_status = "challenge"
                log.warning(
                    "Cloudflare Turnstile detected! User needs to solve "
                    "the challenge in the Chromium window."
                )
                # Don't wait here — return immediately.
                # The frontend will poll /api/warmup-status
                return False
            else:
                self._warmup_status = "solved"
                log.success("No challenge — direct access OK. Warm-up complete!")
                return True

        except Exception as exc:
            log.error("Warm-up navigation error: {}", exc)
            self._warmup_status = "failed"
            return False

    async def check_warmup_solved(self) -> bool:
        """
        Check if the Cloudflare challenge has been solved.
        Called periodically by the frontend via /api/warmup-status.
        """
        if self._warmup_status == "solved":
            return True

        if not self._warmup_page:
            return False

        try:
            html = await self._warmup_page.content()

            if not self._is_cloudflare_challenge(html):
                # Challenge is solved!
                self._warmup_status = "solved"
                log.success("Cloudflare challenge solved! Cookies saved.")
                # Close the warm-up page to save resources
                try:
                    await self._warmup_page.close()
                except Exception:
                    pass
                self._warmup_page = None
                return True
        except Exception as exc:
            log.debug("Warm-up check error: {}", exc)

        return False

    @staticmethod
    def _is_cloudflare_challenge(html: str) -> bool:
        """Check if the HTML contains a Cloudflare challenge page."""
        lower = html.lower()
        return any(marker in lower for marker in [
            "cf-turnstile", "verify you are human", "just a moment",
            "checking your browser", "cf_chl_opt", "cf-challenge-running",
        ])

    # ─── Cookie Inspection ────────────────────────────────────────────────────

    async def has_cf_clearance(self) -> bool:
        """Check if cf_clearance cookie exists in the persistent context."""
        if not self._context:
            return False
        try:
            cookies = await self._context.cookies()
            return any(c["name"] == "cf_clearance" for c in cookies)
        except Exception:
            return False

    # ─── Human Simulation ─────────────────────────────────────────────────────

    async def human_scroll(self, page: Page, scrolls: int = 3) -> None:
        """Scroll the page naturally to mimic reading behaviour."""
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
        """Move mouse randomly across the viewport."""
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
