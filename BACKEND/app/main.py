"""
app/main.py — FastAPI Application Entry Point (v2)

Perubahan dari v1:
- Menggunakan BrowserManagerService untuk startup (load cookies + apply ke context)
- Routes modular (routes/warmup.py, routes/search.py, routes/detail.py)
- Backward compat: api/routes.py masih terdaftar
- CORS middleware dengan konfigurasi yang lebih lengkap
- Graceful shutdown dengan cookie sync
- Screenshot directory auto-created
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.database import db
from app.scraper.browser import browser_manager
from app.services.browser_manager import browser_manager_service
from app.services.cookie_manager import cookie_manager
from app.utils.environment import (
    get_python_executable,
    get_playwright_version,
    get_python_version,
    get_recommended_python,
    is_recommended_python,
)
from app.utils.logger import log


# ─── Lifespan ─────────────────────────────────────────────────────────────────

def _log_environment_startup() -> None:
    python_version = get_python_version()
    python_executable = get_python_executable()
    playwright_version = get_playwright_version()

    log.info("Python runtime: {}", python_version)
    log.info("Python executable: {}", python_executable)
    if not is_recommended_python():
        log.warning(
            "Recommended Python {} for Playwright on Windows, but current runtime is {}.",
            get_recommended_python(),
            python_version,
        )
    else:
        log.info("Recommended Python runtime detected: {}", python_version)

    log.info("Playwright package version: {}", playwright_version)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown lifecycle.

    Startup flow:
    1. Init database (create tables)
    2. Launch browser (Chromium)
    3. Load cookies dari disk → apply ke browser context
    4. Jika cf_clearance valid → siap scraping tanpa warmup
    5. Jika tidak → log warning, minta warmup via API

    Shutdown flow:
    1. Sync cookies terakhir ke disk
    2. Stop browser
    """
    log.info("=" * 65)
    _log_environment_startup()
    log.info("  Mahkamah Agung Scraper v2.0 — Starting Up")
    log.info("  Server  : http://{}:{}", settings.host, settings.port)
    log.info("  Headless: {} | Target: {}", settings.headless, settings.direktori_url)
    log.info("=" * 65)

    # ── 1. Database ────────────────────────────────────────────────────────────
    try:
        await db.init()
        log.success("Database ready: {}", settings.db_path)
    except Exception as exc:
        log.error("Database init gagal: {}", exc)

    # ── 2. Browser + Cookie Load ───────────────────────────────────────────────
    try:
        startup_result = await browser_manager_service.initialize()
        log.info("Browser launch status: {}", startup_result)
        if startup_result.get("session_valid"):
            log.success(
                "✅ Session Cloudflare valid! Siap scraping tanpa warmup."
            )
        else:
            log.warning(
                "⚠️  Session tidak valid / tidak ada cf_clearance. "
                "Panggil POST /api/warmup untuk bypass Cloudflare."
            )
    except Exception as exc:
        log.warning("Browser startup deferred: {} — akan start saat request pertama", exc)

    # ── 3. Ensure directories ──────────────────────────────────────────────────
    (Path(settings.data_dir) / "screenshots").mkdir(parents=True, exist_ok=True)
    Path("cookies").mkdir(exist_ok=True)

    log.info("-" * 65)
    log.info("  API Docs: http://{}:{}/docs", settings.host, settings.port)
    log.info("  POST /api/warmup     — Mulai Cloudflare bypass")
    log.info("  GET  /api/warmup-status — Poll status warmup")
    log.info("  GET  /api/search?q=  — Cari putusan")
    log.info("  GET  /api/health     — Health check")
    log.info("-" * 65)

    yield  # ← aplikasi berjalan

    # ── Shutdown ───────────────────────────────────────────────────────────────
    log.info("Shutting down — syncing cookies...")
    if browser_manager.is_ready and browser_manager._context:
        try:
            await cookie_manager.sync_from_context(browser_manager._context)
            log.success("Cookies synced to disk on shutdown")
        except Exception as exc:
            log.warning("Cookie sync on shutdown gagal: {}", exc)

    await browser_manager.stop()
    log.info("👋 Goodbye! Server stopped.")


# ─── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Direktori Putusan Mahkamah Agung — API",
    description=(
        "Production-ready web scraping API untuk putusan pengadilan Indonesia.\n\n"
        "**Fitur:**\n"
        "- Bypass Cloudflare Challenge & Turnstile\n"
        "- Persistent session dengan cookie management\n"
        "- Auto warmup & session validation\n"
        "- Real-time scraping + SQLite cache\n"
        "- Stealth browser fingerprinting"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if not cors_origins or cors_origins == [""]:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)

# ─── API Routes (Modular) ─────────────────────────────────────────────────────
from app.routes.warmup import router as warmup_router
from app.routes.search import router as search_router
from app.routes.detail import router as detail_router

app.include_router(warmup_router)
app.include_router(search_router)
app.include_router(detail_router)

# Backward compat: tetap daftarkan api/routes.py (ada endpoint /api/lokasi + /api/search POST)
try:
    from app.api.routes import router as legacy_router
    # Hanya tambahkan route yang tidak ada di modular routes
    # (FastAPI otomatis skip duplicate path)
    app.include_router(legacy_router, include_in_schema=False)
except ImportError:
    pass

# ─── Serve Frontend ───────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "FRONTEND"
if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
    log.info("Frontend served from {}", FRONTEND_DIR)
else:
    log.warning("Frontend dir tidak ditemukan: {} — API-only mode", FRONTEND_DIR)


# ─── CLI Entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )
