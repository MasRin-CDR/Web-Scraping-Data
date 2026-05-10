"""
main.py — FastAPI Application Entry Point
Configures CORS, lifespan (browser + DB), static file serving, and API routing.
"""

from __future__ import annotations

import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings
from app.models.database import db
from app.scraper.browser import browser_manager
from app.utils.logger import log


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for browser and database."""
    log.info("=" * 60)
    log.info("Mahkamah Agung Scraper — starting up")
    log.info("Server: http://{}:{}", settings.host, settings.port)
    log.info("=" * 60)

    # Init database
    await db.init()
    log.success("Database ready")

    # Start browser (lazy — can also be started on first request)
    try:
        await browser_manager.start()
    except Exception as exc:
        log.warning("Browser startup deferred: {} — will start on first request", exc)

    yield  # ← app is running

    # Shutdown
    log.info("Shutting down…")
    await browser_manager.stop()
    log.info("Goodbye 👋")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Direktori Putusan Mahkamah Agung — API",
    description="Real-time web scraping API for Indonesian court decisions",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ────────────────────────────────────────────────────────────────
app.include_router(api_router)

# ── Serve Frontend Static Files ───────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "FRONTEND"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    log.info("Frontend served from {}", FRONTEND_DIR)


# ─── CLI Entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
