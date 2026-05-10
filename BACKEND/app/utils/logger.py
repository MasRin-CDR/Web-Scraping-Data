"""
utils/logger.py — Structured Logging with Loguru
Console + rotating file + error-only file.
"""

import sys
from loguru import logger
from app.config import settings


def setup_logger(name: str = "mahkamah") -> "logger":
    """Configure loguru: coloured console, rotating files, separate error log."""
    logger.remove()

    fmt_console = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    fmt_file = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    # Console
    logger.add(
        sys.stdout,
        format=fmt_console,
        level=settings.log_level,
        colorize=True,
        enqueue=True,
    )

    # Main log file
    logger.add(
        settings.log_dir / f"{name}.log",
        format=fmt_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    # Error-only file
    logger.add(
        settings.log_dir / f"{name}_errors.log",
        format=fmt_file,
        level="ERROR",
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    return logger


log = setup_logger()
