"""
routes/warmup.py — Cloudflare Warmup Endpoints

Endpoints:
  POST /api/warmup          → Mulai proses warmup browser
  GET  /api/warmup-status   → Poll status warmup
  POST /api/warmup/reset    → Reset warmup state
  GET  /api/browser-status  → Status detail browser + session
  GET  /api/health          → Health check sistem
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.scraper.browser import browser_manager as bm
from app.services.browser_manager import browser_manager_service
from app.services.cookie_manager import cookie_manager
from app.utils.environment import (
    get_chromium_executable_path,
    get_playwright_version,
    get_python_version,
    get_recommended_python,
    is_recommended_python,
)
from app.utils.logger import log

router = APIRouter(prefix="/api", tags=["Warmup & Browser"])


def _get_runtime_status() -> Dict[str, str]:
    python_version = get_python_version()
    recommended = get_recommended_python()
    return {
        "python_version": python_version,
        "recommended_python": recommended,
        "playwright_version": get_playwright_version(),
        "python_status": "ok" if is_recommended_python() else "warning",
    }


async def _get_chromium_runtime_info() -> Dict[str, str]:
    chromium_executable = get_chromium_executable_path(bm._playwright)
    chromium_version = "<unknown>"
    if bm._context:
        try:
            browser = bm._context.browser
            chromium_version = (
                await browser.version()
                if browser is not None
                else "<persistent-context>"
            )
        except Exception:
            chromium_version = "<unknown>"
    return {
        "chromium_executable": chromium_executable or "<unknown>",
        "chromium_version": chromium_version,
        "browser_launch_status": "ready" if bm.is_ready else "stopped",
    }


# ─── Health Check ─────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """
    Endpoint health check.
    Cek status browser, database, dan cf_clearance cookie.
    """
    has_cf = await bm.has_cf_clearance()
    from app.models.database import db
    db_ok = True
    try:
        await db.init()
    except Exception:
        db_ok = False

    runtime = _get_runtime_status()
    chromium_info = await _get_chromium_runtime_info()

    return {
        "success": True,
        "status": "ok",
        "version": "2.0.0",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "browser_ready": bm.is_ready,
        "database_ready": db_ok,
        "cf_clearance": has_cf,
        "warmup_status": bm.warmup_status,
        "session_valid": has_cf,
        "needs_warmup": not has_cf,
        **runtime,
        **chromium_info,
    }


# ─── Warmup ───────────────────────────────────────────────────────────────────

@router.post("/warmup")
async def start_warmup():
    """
    Mulai proses Cloudflare warmup.

    Flow:
    1. Jika session masih valid → return status=already_ok
    2. Launch browser jika belum jalan
    3. Buka halaman target
    4. Jika tidak ada challenge → return status=ok, session ready
    5. Jika ada Turnstile challenge → return status=challenge
       (user harus solve manual di jendela Chromium, lalu poll /api/warmup-status)

    Response:
      status: "already_ok" | "solved" | "challenge" | "failed"
    """
    log.info("POST /api/warmup — memulai warmup")
    try:
        result = await browser_manager_service.start_warmup()
        log.info("Warmup result: status={}", result.get("status"))
        return {
            "success": result.get("success", False),
            "status": result.get("status", "failed"),
            "message": result.get("message", ""),
            "cf_clearance": result.get("cf_clearance", False),
            "screenshot": result.get("screenshot"),
            "attempt": result.get("attempt", 1),
        }
    except Exception as exc:
        log.exception("Warmup endpoint error: {}", exc)
        raise HTTPException(status_code=500, detail=f"Warmup gagal: {exc}")


@router.get("/warmup-status")
async def get_warmup_status():
    """
    Poll status warmup saat ini.

    Frontend harus poll endpoint ini setiap 2-3 detik saat status=challenge.
    Jika user sudah solve Turnstile di jendela Chromium, status akan berubah ke "solved".

    Response:
      status: "idle" | "warming" | "challenge" | "solved" | "failed"
    """
    try:
        result = await browser_manager_service.check_warmup_status()
        return result
    except Exception as exc:
        log.exception("Warmup status error: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/warmup/reset")
async def reset_warmup():
    """
    Reset warmup state (tanpa restart browser).
    Berguna jika ingin force warmup ulang.
    """
    log.info("POST /api/warmup/reset")
    bm.warmup_status = "idle"
    return {
        "success": True,
        "status": "idle",
        "message": "Warmup state di-reset. Panggil POST /api/warmup untuk mulai ulang.",
    }


# ─── Browser Status ───────────────────────────────────────────────────────────

@router.get("/browser-status")
async def browser_status():
    """
    Status detail browser dan session Cloudflare.

    Return informasi:
    - Apakah browser running
    - Warmup status
    - cf_clearance ada/tidak + kapan expired
    - Jumlah tab terbuka
    - Waktu start browser
    - Cookie info
    """
    try:
        status = await browser_manager_service.get_browser_status()
        status.update(_get_runtime_status())
        status.update(await _get_chromium_runtime_info())
        return {"success": True, "data": status}
    except Exception as exc:
        log.error("Browser status error: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Cookie Management ────────────────────────────────────────────────────────

@router.get("/cookie-status")
async def cookie_status():
    """
    Status cookie Cloudflare yang tersimpan di disk.
    Berguna untuk debugging session persistence.
    """
    return {
        "success": True,
        "data": cookie_manager.status_dict(),
    }


@router.delete("/cookies")
async def clear_cookies():
    """
    Hapus semua cookie yang tersimpan.
    Gunakan ini jika ingin force warmup ulang dari awal.
    """
    log.warning("DELETE /api/cookies — menghapus semua cookie")
    await cookie_manager.clear()
    bm.warmup_status = "idle"
    return {
        "success": True,
        "message": "Cookie dihapus. Warmup diperlukan ulang.",
    }


@router.post("/cookies/sync")
async def sync_cookies():
    """
    Sync cookie dari browser context ke disk secara manual.
    Berguna untuk memastikan cookie tersimpan setelah warmup.
    """
    if not bm.is_ready or not bm._context:
        raise HTTPException(status_code=400, detail="Browser tidak running")

    await cookie_manager.sync_from_context(bm._context)
    return {
        "success": True,
        "message": "Cookie berhasil di-sync ke disk",
        "cookie_info": cookie_manager.status_dict(),
    }


# ─── Screenshot ───────────────────────────────────────────────────────────────

@router.get("/screenshot")
async def get_last_screenshot():
    """
    Return screenshot terakhir yang diambil saat challenge.
    Berguna untuk debugging visual.
    """
    last = browser_manager_service._last_screenshot
    if not last:
        raise HTTPException(status_code=404, detail="Tidak ada screenshot tersedia")

    from pathlib import Path
    path = Path(last)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File screenshot tidak ditemukan")

    return FileResponse(str(path), media_type="image/png")
