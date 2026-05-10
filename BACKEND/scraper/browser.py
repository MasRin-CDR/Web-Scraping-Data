"""
scraper/browser.py - Stealth Chromium Browser Manager
Handles browser lifecycle, stealth injection, and session cookies.
"""

from __future__ import annotations

import asyncio
import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from config import CHROMIUM_ARGS, settings
from utils.helpers import get_random_user_agent, random_delay
from utils.logger import log

# ─── Stealth JS Injection ─────────────────────────────────────────────────────
# Bypasses common bot-detection fingerprinting checks
STEALTH_SCRIPT = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// Override navigator.plugins (empty in headless)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ];
        plugins.refresh = () => {};
        plugins.item = (i) => plugins[i];
        plugins.namedItem = (n) => plugins.find(p => p.name === n);
        return plugins;
    }
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['id-ID', 'id', 'en-US', 'en'],
});

// Override permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);

// Override chrome object
window.chrome = {
    runtime: {},
    loadTimes: () => ({}),
    csi: () => ({}),
    app: {},
};

// Fix iframe contentWindow.navigator.webdriver
const iframeDesc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'contentWindow');
Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get: function () {
        const win = iframeDesc.get.call(this);
        try {
            Object.defineProperty(win.navigator, 'webdriver', {
                get: () => undefined,
            });
        } catch (_) {}
        return win;
    },
});

// Randomize canvas fingerprint
const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
    const imageData = originalGetImageData.call(this, x, y, w, h);
    for (let i = 0; i < imageData.data.length; i += 4) {
        imageData.data[i]     += Math.floor(Math.random() * 3) - 1;
        imageData.data[i + 1] += Math.floor(Math.random() * 3) - 1;
        imageData.data[i + 2] += Math.floor(Math.random() * 3) - 1;
    }
    return imageData;
};
"""


class BrowserManager:
    """
    Manages a single Playwright browser instance with stealth settings.
    Supports context reuse for session cookie persistence.
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._user_agent = get_random_user_agent()

    async def start(self) -> None:
        """Launch Chromium with stealth configuration."""
        log.info("Launching Chromium | headless={} | ua={:.60s}…",
                 settings.headless, self._user_agent)

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless,
            args=CHROMIUM_ARGS,
            timeout=settings.browser_timeout,
        )

        self._context = await self._browser.new_context(
            user_agent=self._user_agent,
            viewport={"width": random.randint(1280, 1920), "height": random.randint(768, 1080)},
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
        )

        # Inject stealth script on every new page
        await self._context.add_init_script(STEALTH_SCRIPT)

        # Block unnecessary resources to speed up loading
        await self._context.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,otf}",
            lambda route: route.abort(),
        )

        log.success("Browser ready")

    async def new_page(self) -> Page:
        """Create a new page with stealth and timeout configured."""
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")
        page = await self._context.new_page()
        page.set_default_timeout(settings.browser_timeout)
        page.set_default_navigation_timeout(settings.browser_timeout)
        return page

    async def stop(self) -> None:
        """Gracefully close browser and playwright instance."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        log.info("Browser closed")

    async def save_cookies(self, path: str = "session_cookies.json") -> None:
        """Persist session cookies to disk."""
        import json
        if self._context:
            cookies = await self._context.cookies()
            with open(path, "w") as f:
                json.dump(cookies, f, indent=2)
            log.debug("Session cookies saved to {}", path)

    async def load_cookies(self, path: str = "session_cookies.json") -> None:
        """Load previously saved cookies into the current context."""
        import json
        from pathlib import Path
        if self._context and Path(path).exists():
            with open(path) as f:
                cookies = json.load(f)
            await self._context.add_cookies(cookies)
            log.debug("Session cookies loaded from {} ({} entries)", path, len(cookies))

    # ── Context manager support ───────────────────────────────────────────────
    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()
