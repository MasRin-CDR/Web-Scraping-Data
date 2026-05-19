"""Windows asyncio defaults for Playwright subprocess support.

Python imports this module automatically when the backend directory is on
``sys.path``. Uvicorn reload can otherwise run with a selector loop on Windows,
which does not support ``asyncio.create_subprocess_exec`` used by Playwright.
"""

from __future__ import annotations

import asyncio
import sys


if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
