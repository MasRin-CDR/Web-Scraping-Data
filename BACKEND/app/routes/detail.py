"""
routes/detail.py — Detail & PDF Endpoints

Endpoints:
  GET  /api/detail?id=<url>     → Ambil detail putusan
  POST /api/detail              → POST version (body: {url})
  GET  /api/download-pdf?url=.. → Download PDF via browser proxy
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.models.schemas import DetailRequest, DetailResponse
from app.scraper.browser import browser_manager as bm
from app.services.cloudflare_service import cloudflare_service
from app.services.search_service import search_service
from app.utils.logger import log

router = APIRouter(prefix="/api", tags=["Detail & PDF"])


# ─── Detail ───────────────────────────────────────────────────────────────────

@router.get("/detail", response_model=DetailResponse)
async def get_detail_get(
    url: str = Query(..., description="URL halaman detail putusan"),
):
    """
    Ambil detail lengkap satu putusan via URL (GET version).

    Flow:
    1. Cek cache database — jika ada detail lengkap, return langsung
    2. Jika cache miss → scrape halaman detail
    3. Cek CF challenge → return error jika terblokir
    4. Parse metadata, amar, hakim, dll.
    5. Simpan ke database

    Response: PutusanDetail object
    """
    log.info("GET /api/detail | url={:.60s}", url)

    if not bm.is_ready:
        return DetailResponse(
            success=False,
            message="Browser belum siap. Panggil POST /api/warmup terlebih dahulu.",
        )

    has_cf = await bm.has_cf_clearance()
    if not has_cf:
        log.warning("Detail dipanggil tanpa cf_clearance — kemungkinan akan 403")

    try:
        result = await search_service.get_detail(url)

        # Cek apakah error karena CF
        if not result.success and result.message:
            msg_lower = result.message.lower()
            if "cloudflare" in msg_lower or "challenge" in msg_lower:
                return DetailResponse(
                    success=False,
                    message=(
                        "Cloudflare challenge terdeteksi. "
                        "Jalankan POST /api/warmup terlebih dahulu."
                    ),
                )

        return result

    except Exception as exc:
        log.exception("Detail GET error: {}", exc)
        err_str = str(exc).lower()
        if "cloudflare" in err_str or "403" in err_str or "challenge" in err_str:
            return DetailResponse(
                success=False,
                message="Cloudflare challenge terdeteksi. Jalankan /api/warmup.",
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/detail", response_model=DetailResponse)
async def get_detail_post(req: DetailRequest):
    """
    Ambil detail putusan via POST body (backward compat + POST clients).

    Body:
      { "url": "https://putusan3.mahkamahagung.go.id/..." }
    """
    log.info("POST /api/detail | url={:.60s}", req.url)

    if not bm.is_ready:
        return DetailResponse(
            success=False,
            message="Browser belum siap. Panggil POST /api/warmup terlebih dahulu.",
        )

    try:
        result = await search_service.get_detail(req.url)

        if not result.success and result.message:
            msg_lower = result.message.lower()
            if "cloudflare" in msg_lower or "challenge" in msg_lower:
                return DetailResponse(
                    success=False,
                    message=(
                        "Cloudflare challenge terdeteksi. "
                        "Jalankan POST /api/warmup terlebih dahulu."
                    ),
                )

        return result

    except Exception as exc:
        log.exception("Detail POST error: {}", exc)
        err_str = str(exc).lower()
        if "cloudflare" in err_str or "403" in err_str or "challenge" in err_str:
            return DetailResponse(
                success=False,
                message="Cloudflare challenge terdeteksi. Jalankan /api/warmup.",
            )
        raise HTTPException(status_code=500, detail=str(exc))


# ─── PDF Download ─────────────────────────────────────────────────────────────

@router.get("/download-pdf")
async def download_pdf(
    url: str = Query(..., description="URL PDF dari putusan"),
):
    """
    Proxy-download PDF file dari website pengadilan.

    Menggunakan browser context yang sudah warmup (dengan cf_clearance)
    untuk menghindari 403 saat download PDF.

    Return: PDF binary stream untuk langsung dibuka/download oleh browser.
    """
    log.info("GET /api/download-pdf | url={:.60s}", url)

    # Validasi URL
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL tidak valid")

    if not bm.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Browser belum siap. Panggil /api/warmup terlebih dahulu.",
        )

    try:
        pdf_bytes = await search_service.download_pdf(url)

        if not pdf_bytes:
            raise HTTPException(
                status_code=404,
                detail="PDF tidak dapat diunduh. Mungkin URL tidak valid atau akses ditolak.",
            )

        # Derive filename dari URL
        filename = url.split("/")[-1].split("?")[0]
        if not filename.lower().endswith(".pdf"):
            filename = "putusan.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("PDF download error: {}", exc)
        raise HTTPException(status_code=500, detail=f"Gagal download PDF: {exc}")
