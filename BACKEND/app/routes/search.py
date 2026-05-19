"""
routes/search.py — Search Endpoints

Endpoints:
  GET  /api/search?q=keyword&lokasi=...&jenis=...&page=1  → Search putusan
  GET  /api/lokasi                                         → List lokasi pengadilan
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.scraper.browser import browser_manager as bm
from app.services.cloudflare_service import cloudflare_service
from app.services.search_service import search_service
from app.models.schemas import SearchRequest, SearchResponse
from app.utils.logger import log

router = APIRouter(prefix="/api", tags=["Search"])


@router.get("/search", response_model=SearchResponse)
async def search_putusan(
    q: str = Query(default="", description="Kata kunci pencarian"),
    lokasi: str = Query(default="", description="Filter lokasi pengadilan"),
    jenis: str = Query(default="", description="Filter jenis peradilan"),
    page: int = Query(default=1, ge=1, description="Nomor halaman"),
    per_page: int = Query(default=20, ge=1, le=100, description="Hasil per halaman"),
):
    """
    Cari putusan pengadilan secara realtime.

    Flow:
    1. Cek apakah session Cloudflare masih valid
    2. Jika tidak → return error dengan instruksi warmup
    3. Cek cache database dulu (TTL: 1 jam)
    4. Jika cache miss → scrape langsung dari website
    5. Simpan hasil ke database + cache
    6. Return hasil dengan paginasi

    Jika Cloudflare challenge terdeteksi saat scraping:
      → return { success: false, message: "Cloudflare challenge..." }
    """
    log.info("GET /api/search | q='{}' lokasi='{}' jenis='{}' page={}", q, lokasi, jenis, page)

    # Validasi: warmup harus dilakukan dulu
    if not bm.is_ready:
        return SearchResponse(
            success=False,
            message="Browser belum siap. Panggil POST /api/warmup terlebih dahulu.",
            data=[],
        )

    has_cf = await bm.has_cf_clearance()
    if not has_cf:
        log.warning("Search dipanggil tanpa cf_clearance — kemungkinan akan 403")
        # Tidak block — tetap coba, mungkin site tidak pakai CF saat ini

    try:
        req = SearchRequest(
            keyword=q,
            lokasi=lokasi,
            jenis_peradilan=jenis,
            page=page,
            per_page=per_page,
        )
        result = await search_service.search(req)

        # Cek apakah hasil berisi indikasi CF challenge
        if not result.success and result.data == []:
            log.warning("Search return kosong — mungkin CF challenge")

        return result

    except Exception as exc:
        log.exception("Search endpoint error: {}", exc)
        # Cek apakah error karena Cloudflare
        err_msg = str(exc).lower()
        if "cloudflare" in err_msg or "403" in err_msg or "challenge" in err_msg:
            return SearchResponse(
                success=False,
                message=(
                    "Cloudflare challenge terdeteksi. "
                    "Jalankan POST /api/warmup terlebih dahulu."
                ),
                data=[],
            )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/search", response_model=SearchResponse)
async def search_putusan_post(req: SearchRequest):
    """
    POST version dari /api/search (untuk kompatibilitas backward).
    Gunakan GET /api/search untuk request baru.
    """
    log.info(
        "POST /api/search | keyword='{}' lokasi='{}' page={}",
        req.keyword, req.lokasi, req.page,
    )

    if not bm.is_ready:
        return SearchResponse(
            success=False,
            message="Browser belum siap. Panggil POST /api/warmup terlebih dahulu.",
            data=[],
        )

    try:
        return await search_service.search(req)
    except Exception as exc:
        log.exception("Search POST error: {}", exc)
        err_msg = str(exc).lower()
        if "cloudflare" in err_msg or "403" in err_msg or "challenge" in err_msg:
            return SearchResponse(
                success=False,
                message="Cloudflare challenge terdeteksi. Jalankan /api/warmup.",
                data=[],
            )
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Lokasi Dropdown ──────────────────────────────────────────────────────────

@router.get("/lokasi")
async def get_lokasi_list():
    """
    Return daftar lokasi pengadilan untuk dropdown filter frontend.
    Data diambil dari FRONTEND/app.js (sync otomatis).
    """
    lokasi = _load_frontend_lokasi_list()
    return {
        "success": True,
        "data": lokasi,
        "total": len(lokasi),
    }


def _load_frontend_lokasi_list() -> list[str]:
    """Sync lokasi list dari frontend JavaScript source."""
    frontend_js = Path(__file__).resolve().parents[3] / "FRONTEND" / "app.js"
    fallback = [
        "MAHKAMAH AGUNG",
        "PENGADILAN PAJAK",
        "PENGADILAN NEGERI JAKARTA PUSAT",
        "PENGADILAN TINGGI JAKARTA",
    ]
    try:
        text = frontend_js.read_text(encoding="utf-8")
        match = re.search(r"const\s+LOKASI_LIST\s*=\s*\[(.*?)\];", text, re.S)
        if not match:
            return fallback
        items = re.findall(r"'([^']+)'", match.group(1))
        return sorted(dict.fromkeys(items), key=str.casefold)
    except Exception as exc:
        log.warning("Failed loading frontend lokasi list: {}", exc)
        return fallback
