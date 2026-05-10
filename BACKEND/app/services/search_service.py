"""
services/search_service.py — Search Business Logic
Orchestrates cache lookup → live scraping → DB persistence → response.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.database import db
from app.models.schemas import (
    DetailResponse,
    PutusanDetail,
    PutusanItem,
    SearchRequest,
    SearchResponse,
)
from app.scraper.engine import scraping_engine
from app.utils.logger import log


class SearchService:
    """
    Service layer between API routes and scraping / database.
    Flow: cache → live scrape → save to DB → return paginated response.
    """

    # ─── Search ───────────────────────────────────────────────────────────────

    async def search(self, req: SearchRequest) -> SearchResponse:
        """
        Execute a putusan search.
        1. Check cache
        2. If miss → live scrape
        3. Save results to DB
        4. Return paginated response
        """
        keyword = req.keyword.strip()
        lokasi = req.lokasi.strip()
        jenis = req.jenis_peradilan.strip()

        # 1. Check cache
        cached = await db.get_cache(keyword, lokasi, jenis)
        if cached:
            log.info("Cache HIT | keyword='{}' lokasi='{}' ({} items)", keyword, lokasi, len(cached))
            await db.log_search(keyword, lokasi, jenis, len(cached), source="cache")
            return self._paginate(cached, req.page, req.per_page, source="cache")

        # 2. Live scrape
        log.info("Cache MISS — starting live scrape | keyword='{}' lokasi='{}'", keyword, lokasi)
        try:
            raw_records = await scraping_engine.search(
                keyword=keyword,
                lokasi=lokasi,
                jenis=jenis,
                max_pages=settings.max_pages_per_search,
            )
        except Exception as exc:
            log.error("Live scrape failed: {}", exc)
            # Fallback: try database
            return await self._fallback_db_search(req)

        if not raw_records:
            log.warning("No records found via scraping — trying DB fallback")
            return await self._fallback_db_search(req)

        # 3. Save to DB + cache
        await db.bulk_upsert(raw_records)
        await db.set_cache(keyword, lokasi, jenis, raw_records)
        await db.log_search(keyword, lokasi, jenis, len(raw_records), source="live")

        log.info("Scraped {} records — saved to DB + cache", len(raw_records))
        return self._paginate(raw_records, req.page, req.per_page, source="live")

    # ─── Detail ───────────────────────────────────────────────────────────────

    async def get_detail(self, url: str) -> DetailResponse:
        """Fetch detail for a specific putusan by its URL."""
        # Check DB first
        existing = await db.get_putusan_by_url(url)
        if existing and existing.get("amar_putusan"):
            log.info("Detail from DB cache | url={:.50s}", url)
            return DetailResponse(
                success=True,
                data=self._to_detail(existing),
                message="Data dari cache database",
            )

        # Live scrape detail page
        log.info("Scraping detail page | url={:.50s}", url)
        try:
            raw = await scraping_engine.get_detail(url)
        except Exception as exc:
            log.error("Detail scrape failed: {}", exc)
            return DetailResponse(success=False, message=f"Gagal mengambil detail: {exc}")

        if raw.get("error"):
            return DetailResponse(success=False, message=raw["error"])

        # Save enriched data
        if raw.get("nomor_perkara"):
            await db.upsert_putusan(raw)

        return DetailResponse(
            success=True,
            data=self._to_detail(raw),
            message="Data berhasil diambil",
        )

    # ─── PDF ──────────────────────────────────────────────────────────────────

    async def download_pdf(self, url: str) -> Optional[bytes]:
        """Download a PDF file and return its bytes."""
        return await scraping_engine.download_pdf(url)

    # ─── Fallback DB Search ───────────────────────────────────────────────────

    async def _fallback_db_search(self, req: SearchRequest) -> SearchResponse:
        """Search from locally cached database records."""
        rows, total = await db.search_putusan(
            keyword=req.keyword,
            lokasi=req.lokasi,
            jenis=req.jenis_peradilan,
            page=req.page,
            per_page=req.per_page,
        )
        if rows:
            log.info("DB fallback returned {} results", len(rows))
            return self._paginate(rows, req.page, req.per_page, source="database", total_override=total)

        return SearchResponse(
            success=True,
            total=0,
            page=req.page,
            per_page=req.per_page,
            total_pages=0,
            data=[],
            source="live",
            message="Tidak ada hasil ditemukan. Coba kata kunci lain.",
            scraped_at=datetime.utcnow().isoformat(),
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _paginate(
        self,
        records: List[Dict],
        page: int,
        per_page: int,
        source: str = "live",
        total_override: Optional[int] = None,
    ) -> SearchResponse:
        """Convert raw records into a paginated SearchResponse."""
        total = total_override if total_override is not None else len(records)
        total_pages = math.ceil(total / per_page) if per_page > 0 else 0

        start = (page - 1) * per_page
        end = start + per_page
        page_data = records[start:end] if total_override is None else records

        items = [self._to_item(r) for r in page_data]

        return SearchResponse(
            success=True,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=items,
            source=source,
            scraped_at=datetime.utcnow().isoformat(),
            message=f"{total} hasil ditemukan" if total > 0 else "Tidak ada hasil",
        )

    @staticmethod
    def _to_item(raw: Dict[str, Any]) -> PutusanItem:
        return PutusanItem(
            id=raw.get("id"),
            nomor_perkara=raw.get("nomor_perkara", ""),
            tahun=raw.get("tahun"),
            lokasi=raw.get("lokasi", ""),
            jenis_peradilan=raw.get("jenis_peradilan", ""),
            judul=raw.get("judul", ""),
            tanggal_putusan=raw.get("tanggal_putusan"),
            status=raw.get("status", ""),
            url_detail=raw.get("url_detail"),
            url_pdf=raw.get("url_pdf"),
        )

    @staticmethod
    def _to_detail(raw: Dict[str, Any]) -> PutusanDetail:
        import json
        metadata = raw.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        return PutusanDetail(
            nomor_perkara=raw.get("nomor_perkara", ""),
            tahun=raw.get("tahun"),
            lokasi=raw.get("lokasi", ""),
            jenis_peradilan=raw.get("jenis_peradilan", ""),
            judul=raw.get("judul", ""),
            tanggal_putusan=raw.get("tanggal_putusan"),
            tanggal_register=raw.get("tanggal_register"),
            status=raw.get("status", ""),
            hakim=raw.get("hakim"),
            panitera=raw.get("panitera"),
            amar_putusan=raw.get("amar_putusan"),
            klasifikasi=raw.get("klasifikasi"),
            sub_klasifikasi=raw.get("sub_klasifikasi"),
            tingkat_proses=raw.get("tingkat_proses"),
            url_detail=raw.get("url_detail"),
            url_pdf=raw.get("url_pdf"),
            para_pihak=raw.get("para_pihak"),
            catatan=raw.get("catatan"),
            metadata=metadata,
        )


# ─── Singleton ────────────────────────────────────────────────────────────────
search_service = SearchService()
