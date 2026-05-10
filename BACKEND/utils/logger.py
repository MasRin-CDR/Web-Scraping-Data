"""
utils/logger.py - Structured Logging Configuration
Uses loguru for rich, structured logging with rotation.
"""

import sys
from pathlib import Path

from loguru import logger

from config import settings


def setup_logger(name: str = "scraper") -> "logger":
    """
    Configure and return a loguru logger instance.

    Features:
    - Console output with colors and formatting
    - Rotating file logs (daily, 10 MB max)
    - Separate error log file
    - JSON-friendly structured format for files
    """
    logger.remove()  # Remove default handler

    log_format_console = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    log_format_file = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # ── Console handler ───────────────────────────────────────────────────────
    logger.add(
        sys.stdout,
        format=log_format_console,
        level=settings.log_level,
        colorize=True,
        enqueue=True,
    )

    # ── Main log file (rotating daily, 10 MB max, keep 30 days) ──────────────
    log_file = settings.log_dir / f"{name}.log"
    logger.add(
        log_file,
        format=log_format_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    # ── Error-only log file ───────────────────────────────────────────────────
    error_log_file = settings.log_dir / f"{name}_errors.log"
    logger.add(
        error_log_file,
        format=log_format_file,
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    logger.info(f"Logger initialized | level={settings.log_level} | file={log_file}")
    return logger


# ─── Module-level logger ──────────────────────────────────────────────────────
log = setup_logger()
