"""Environment helpers untuk startup validation dan status reporting."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from typing import Optional


RECOMMENDED_PYTHON = (3, 11)


def get_python_version() -> str:
    """Return current Python runtime version string."""
    return sys.version.split()[0]


def get_python_executable() -> str:
    """Return the active Python executable path."""
    return sys.executable


def is_recommended_python() -> bool:
    """Return whether the current Python runtime matches the recommended version."""
    return sys.version_info[:2] == RECOMMENDED_PYTHON


def get_recommended_python() -> str:
    """Return the recommended Python version string."""
    return f"{RECOMMENDED_PYTHON[0]}.{RECOMMENDED_PYTHON[1]}"


def get_playwright_version() -> str:
    """Return installed Playwright package version, or a placeholder if missing."""
    try:
        return version("playwright")
    except PackageNotFoundError:
        return "<not installed>"
    except Exception:
        return "<unknown>"


def get_chromium_executable_path(playwright_obj: object) -> Optional[str]:
    """Return the Chromium executable path from Playwright, if available."""
    if not playwright_obj:
        return None
    return getattr(playwright_obj.chromium, "executable_path", None)


async def get_browser_version(context: object) -> str:
    """Return Chromium browser version from an active Playwright context."""
    if not context:
        return "<unknown>"
    try:
        return await context.browser.version()
    except Exception:
        return "<unknown>"
