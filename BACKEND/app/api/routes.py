"""
api/routes.py — FastAPI Route Definitions
All API endpoints for the Mahkamah Agung scraper frontend.
Includes warm-up endpoints for Cloudflare Turnstile bypass.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.models.schemas import (
    DetailRequest,
    DetailResponse,
    ErrorResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
)
from app.scraper.browser import browser_manager
from app.services.search_service import search_service
from app.utils.logger import log

router = APIRouter(prefix="/api", tags=["Scraper API"])


# ─── Health Check ─────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Application health check."""
    has_cf = await browser_manager.has_cf_clearance()
    return HealthResponse(
        status="ok",
        browser_ready=browser_manager.is_ready,
        database_ready=True,
        cf_clearance=has_cf,
    )


# ─── Warm-Up (Cloudflare Bypass) ─────────────────────────────────────────────

@router.post("/warmup")
async def warmup():
    """
    Start the Cloudflare warm-up process.
    Opens the target website in the Playwright browser.
    If Cloudflare Turnstile appears, the user must solve it
    in the visible Chromium window.
    """
    log.info("API /warmup | Starting warm-up process")

    if not browser_manager.is_ready:
        try:
            await browser_manager.start()
        except Exception as exc:
            log.exception("Browser startup failed during warm-up: {}", exc)
            raise HTTPException(status_code=503, detail=f"Browser not ready: {exc}")

    # Check if already warmed up
    has_cf = await browser_manager.has_cf_clearance()
    if has_cf and browser_manager.warmup_status == "solved":
        return {
            "status": "solved",
            "message": "Sudah terverifikasi — siap untuk pencarian",
        }

    result = await browser_manager.warmup()
    return {
        "status": browser_manager.warmup_status,
        "message": _warmup_message(browser_manager.warmup_status),
        "direct_access": result,
    }


@router.get("/warmup-status")
async def warmup_status():
    """
    Check the current warm-up status.
    Frontend polls this endpoint to know when the challenge is solved.
    """
    status = browser_manager.warmup_status

    if status == "challenge":
        # Check if user has solved it
        solved = await browser_manager.check_warmup_solved()
        if solved:
            status = "solved"

    has_cf = await browser_manager.has_cf_clearance()

    return {
        "status": status,
        "cf_clearance": has_cf,
        "message": _warmup_message(status),
    }


def _warmup_message(status: str) -> str:
    messages = {
        "idle": "Warm-up belum dimulai. Klik tombol untuk memulai.",
        "warming": "Sedang membuka halaman target…",
        "challenge": "⚠️ Cloudflare Turnstile terdeteksi! Selesaikan verifikasi di jendela Chromium yang muncul.",
        "solved": "✅ Verifikasi berhasil! Siap untuk pencarian.",
        "failed": "❌ Warm-up gagal. Coba lagi.",
    }
    return messages.get(status, "Status tidak diketahui")


# ─── Search ───────────────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse)
async def search_putusan(req: SearchRequest):
    """
    Search putusan pengadilan.
    Checks cache first, then performs live scraping if needed.
    Results are persisted in the database for future queries.
    """
    log.info(
        "API /search | keyword='{}' lokasi='{}' jenis='{}' page={}",
        req.keyword, req.lokasi, req.jenis_peradilan, req.page,
    )
    try:
        result = await search_service.search(req)
        return result
    except Exception as exc:
        log.exception("Search endpoint error: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Detail ───────────────────────────────────────────────────────────────────

@router.post("/detail", response_model=DetailResponse)
async def get_detail(req: DetailRequest):
    """
    Get full detail of a specific putusan.
    Scrapes the detail page if not already cached.
    """
    log.info("API /detail | url={:.60s}", req.url)
    try:
        result = await search_service.get_detail(req.url)
        return result
    except Exception as exc:
        log.exception("Detail endpoint error: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── PDF Download ─────────────────────────────────────────────────────────────

@router.get("/download-pdf")
async def download_pdf(url: str = Query(..., description="PDF URL to download")):
    """
    Proxy-download a PDF file from the court website.
    Streams the PDF back to the client browser.
    """
    log.info("API /download-pdf | url={:.60s}", url)
    try:
        pdf_bytes = await search_service.download_pdf(url)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="PDF tidak ditemukan")

        # Derive filename from URL
        filename = url.split("/")[-1] if "/" in url else "putusan.pdf"
        if not filename.endswith(".pdf"):
            filename = "putusan.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("PDF download error: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Lokasi List ──────────────────────────────────────────────────────────────

@router.get("/lokasi")
async def get_lokasi_list():
    """Return the full list of court locations for the frontend dropdown."""
    lokasi = [
        "Mahkamah Agung RI, Jakarta",
        "PN Jakarta Pusat", "PN Jakarta Selatan", "PN Jakarta Utara",
        "PN Jakarta Barat", "PN Jakarta Timur",
        "PN Bandung", "PN Bekasi", "PN Depok", "PN Bogor",
        "PN Tangerang", "PN Tangerang Selatan",
        "PN Surabaya", "PN Malang", "PN Sidoarjo", "PN Gresik", "PN Pasuruan",
        "PN Semarang", "PN Yogyakarta", "PN Klaten", "PN Solo",
        "PN Medan", "PN Deli Serdang", "PN Binjai", "PN Pematangsiantar",
        "PN Makassar", "PN Gowa", "PN Maros",
        "PN Palembang", "PN Prabumulih",
        "PN Pekanbaru", "PN Dumai",
        "PN Banjarmasin", "PN Banjarbaru",
        "PN Balikpapan", "PN Samarinda", "PN Kutai Kartanegara",
        "PN Manado", "PN Bitung",
        "PN Denpasar", "PN Badung", "PN Gianyar",
        "PN Padang", "PN Bukittinggi",
        "PN Pontianak", "PN Singkawang",
        "PN Jambi", "PN Muara Bungo",
        "PN Kupang", "PN Ende",
        "PN Mataram", "PN Selong",
        "PN Ambon", "PN Ternate",
        "PN Jayapura", "PN Sorong", "PN Merauke",
        "PN Bengkulu", "PN Kepahiang",
        "PN Serang", "PN Cilegon",
        "PN Gorontalo", "PN Limboto",
        "PN Kendari", "PN Baubau",
        "PN Palu", "PN Poso",
        "PN Mamuju", "PN Polewali",
        "PN Tanjungpinang", "PN Batam",
        "PA Jakarta Pusat", "PA Jakarta Selatan", "PA Bandung",
        "PA Surabaya", "PA Makassar",
        "PTUN Jakarta", "PTUN Bandung", "PTUN Surabaya",
        "PTUN Medan", "PTUN Makassar",
        "Dilmil I-02 Medan", "Dilmil II-08 Jakarta",
        "Dilmil II-09 Bandung", "Dilmil III-14 Makassar",
    ]
    return {"data": lokasi, "total": len(lokasi)}
