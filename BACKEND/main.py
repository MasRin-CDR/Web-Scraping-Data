"""
main.py - CLI Entry Point for Mahkamah Agung Scraper
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from scraper.scraper import MahkamahScraper
from utils.logger import log

console = Console()


def print_banner() -> None:
    banner = Text()
    banner.append("Mahkamah Agung Direktori Scraper\n", style="bold cyan")
    banner.append("Production-grade async web scraper\n", style="dim")
    banner.append(f"Target: {settings.target_url}\n", style="yellow")
    banner.append(f"Max pages: {settings.max_pages} | ", style="white")
    banner.append(f"Headless: {settings.headless}", style="white")
    console.print(Panel(banner, border_style="cyan"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mahkamah Agung Direktori Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help=f"Max pages to scrape (default: {settings.max_pages})",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip PostgreSQL output",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Skip CSV output",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help="Force headless browser mode",
    )
    return parser.parse_args()


async def main() -> None:
    print_banner()
    args = parse_args()

    # CLI overrides
    if args.headless is not None:
        settings.headless = args.headless

    use_db = not args.no_db
    use_csv = not args.no_csv
    max_pages = args.pages or settings.max_pages

    if not use_db and not use_csv:
        log.error("At least one output target (--db or --csv) must be enabled")
        sys.exit(1)

    scraper = MahkamahScraper(
        use_db=use_db,
        use_csv=use_csv,
        max_pages=max_pages,
    )

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()

    def _shutdown(sig_name: str) -> None:
        log.warning("Received {} — initiating graceful shutdown…", sig_name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig.name: _shutdown(s))
        except (ValueError, NotImplementedError):
            # Windows doesn't support add_signal_handler for all signals
            pass

    try:
        await scraper.run()
    except (asyncio.CancelledError, KeyboardInterrupt):
        log.info("Scraper shut down cleanly")
    except Exception as exc:
        log.exception("Fatal error: {}", exc)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
