"""
scraper/human_simulation.py - Human Behavior Simulation
Simulates realistic mouse movements, scrolling, and interaction patterns.
"""

from __future__ import annotations

import asyncio
import math
import random

from playwright.async_api import Page

from config import settings
from utils.logger import log


class HumanSimulator:
    """
    Provides realistic human-like interaction patterns for a Playwright Page.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    # ─── Scrolling ────────────────────────────────────────────────────────────

    async def scroll_page_naturally(
        self,
        total_scrolls: int | None = None,
        direction: str = "down",
    ) -> None:
        """
        Scroll the page in smooth increments to simulate human reading behavior.
        Random pauses are interspersed to mimic reading.
        """
        viewport_height = self._page.viewport_size["height"] if self._page.viewport_size else 768
        scroll_count = total_scrolls or random.randint(3, 7)

        log.debug("Simulating scroll | direction={} | scrolls={}", direction, scroll_count)

        for i in range(scroll_count):
            # Randomize scroll amount (partial viewport to full viewport)
            scroll_amount = random.randint(
                int(viewport_height * 0.3),
                int(viewport_height * 0.9),
            )
            if direction == "up":
                scroll_amount = -scroll_amount

            await self._page.evaluate(
                f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})"
            )

            # Random pause (mimics reading time)
            pause = random.uniform(
                settings.scroll_delay_min,
                settings.scroll_delay_max,
            )
            await asyncio.sleep(pause)

            # Occasionally pause longer (as if reading something interesting)
            if random.random() < 0.15:
                await asyncio.sleep(random.uniform(1.0, 2.5))

    async def scroll_to_bottom(self) -> None:
        """Scroll all the way to the bottom of the page, naturally."""
        prev_height = -1
        while True:
            current_height = await self._page.evaluate("document.body.scrollHeight")
            if current_height == prev_height:
                break
            prev_height = current_height
            await self.scroll_page_naturally(total_scrolls=2)

    async def scroll_to_element(self, selector: str) -> None:
        """Scroll a specific element into view."""
        element = await self._page.query_selector(selector)
        if element:
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.2, 0.5))

    # ─── Mouse ────────────────────────────────────────────────────────────────

    async def move_mouse_randomly(self, num_moves: int = 3) -> None:
        """
        Move the mouse in random bezier-like curves across the viewport.
        This defeats simple mousemove-detection anti-bot checks.
        """
        vp = self._page.viewport_size or {"width": 1280, "height": 800}
        width, height = vp["width"], vp["height"]

        for _ in range(num_moves):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            steps = random.randint(5, 20)
            await self._page.mouse.move(x, y, steps=steps)
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def hover_element(self, selector: str) -> bool:
        """Hover over an element (helps with lazy-loaded content)."""
        element = await self._page.query_selector(selector)
        if element:
            await element.hover()
            await asyncio.sleep(random.uniform(0.1, 0.4))
            return True
        return False

    # ─── Click ────────────────────────────────────────────────────────────────

    async def human_click(self, selector: str, timeout: int = 10_000) -> bool:
        """
        Click an element with realistic human delay and mouse movement.
        Returns True on success.
        """
        try:
            element = await self._page.wait_for_selector(
                selector, timeout=timeout, state="visible"
            )
            if not element:
                return False

            # Move mouse near the element first
            box = await element.bounding_box()
            if box:
                # Aim slightly off-center (humans don't click exactly in the center)
                x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await self._page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))

            await element.click()
            await asyncio.sleep(random.uniform(0.3, 0.8))
            return True
        except Exception as exc:
            log.debug("human_click failed on '{}': {}", selector, exc)
            return False

    # ─── Navigation ───────────────────────────────────────────────────────────

    async def wait_for_page_stable(self, timeout: int = 15_000) -> None:
        """Wait until network activity settles (networkidle)."""
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            # Fallback to domcontentloaded if networkidle times out
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5_000)
            except Exception:
                pass
