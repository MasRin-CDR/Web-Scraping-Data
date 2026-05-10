"""
models/database.py — Async SQLite Database Layer
Provides caching, logging, and putusan persistence via aiosqlite.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from app.config import settings
from app.utils.logger import log


# ─── DDL ──────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS putusan (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nomor_perkara     TEXT UNIQUE,
    tahun             TEXT,
    lokasi            TEXT,
    jenis_peradilan   TEXT,
    judul             TEXT,
    tanggal_putusan   TEXT,
    tanggal_register  TEXT,
    status            TEXT DEFAULT '',
    hakim             TEXT,
    panitera          TEXT,
    amar_putusan      TEXT,
    klasifikasi       TEXT,
    sub_klasifikasi   TEXT,
    tingkat_proses    TEXT,
    url_detail        TEXT,
    url_pdf           TEXT,
    para_pihak        TEXT,
    metadata_json     TEXT DEFAULT '{}',
    scraped_at        TEXT,
    source_page       INTEGER DEFAULT 1,
    created_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword           TEXT,
    lokasi            TEXT,
    jenis_peradilan   TEXT,
    results_count     INTEGER DEFAULT 0,
    source            TEXT DEFAULT 'live',
    searched_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scrape_cache (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key         TEXT UNIQUE,
    data_json         TEXT,
    total_results     INTEGER DEFAULT 0,
    created_at        TEXT,
    expires_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_putusan_nomor   ON putusan(nomor_perkara);
CREATE INDEX IF NOT EXISTS idx_putusan_lokasi  ON putusan(lokasi);
CREATE INDEX IF NOT EXISTS idx_putusan_jenis   ON putusan(jenis_peradilan);
CREATE INDEX IF NOT EXISTS idx_putusan_tahun   ON putusan(tahun);
CREATE INDEX IF NOT EXISTS idx_cache_key       ON scrape_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires   ON scrape_cache(expires_at);
"""


class Database:
    """Async SQLite wrapper with cache, logging, and CRUD."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or settings.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Create tables and indexes."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.commit()
        log.info("Database initialized at {}", self.db_path)

    # ─── Putusan CRUD ─────────────────────────────────────────────────────────

    async def upsert_putusan(self, data: Dict[str, Any]) -> int:
        """Insert or update a single putusan record. Returns 1 on success."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO putusan (
                    nomor_perkara, tahun, lokasi, jenis_peradilan, judul,
                    tanggal_putusan, tanggal_register, status,
                    hakim, panitera, amar_putusan,
                    klasifikasi, sub_klasifikasi, tingkat_proses,
                    url_detail, url_pdf, para_pihak,
                    metadata_json, scraped_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(nomor_perkara) DO UPDATE SET
                    judul         = excluded.judul,
                    url_pdf       = COALESCE(excluded.url_pdf, putusan.url_pdf),
                    hakim         = COALESCE(excluded.hakim, putusan.hakim),
                    amar_putusan  = COALESCE(excluded.amar_putusan, putusan.amar_putusan),
                    metadata_json = excluded.metadata_json,
                    scraped_at    = excluded.scraped_at
            """, (
                data.get("nomor_perkara"),
                data.get("tahun"),
                data.get("lokasi"),
                data.get("jenis_peradilan"),
                data.get("judul"),
                data.get("tanggal_putusan"),
                data.get("tanggal_register"),
                data.get("status", ""),
                data.get("hakim"),
                data.get("panitera"),
                data.get("amar_putusan"),
                data.get("klasifikasi"),
                data.get("sub_klasifikasi"),
                data.get("tingkat_proses"),
                data.get("url_detail"),
                data.get("url_pdf"),
                data.get("para_pihak"),
                json.dumps(data.get("metadata", {})),
                datetime.utcnow().isoformat(),
            ))
            await conn.commit()
            return conn.total_changes

    async def bulk_upsert(self, records: List[Dict[str, Any]]) -> int:
        """Upsert a batch of putusan records. Returns count saved."""
        saved = 0
        for rec in records:
            try:
                saved += await self.upsert_putusan(rec)
            except Exception as exc:
                log.debug("DB upsert skip: {}", exc)
        return saved

    async def search_putusan(
        self,
        keyword: str = "",
        lokasi: str = "",
        jenis: str = "",
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[List[Dict], int]:
        """Search cached putusan from database. Returns (rows, total_count)."""
        conditions = []
        params: list = []

        if keyword:
            conditions.append(
                "(nomor_perkara LIKE ? OR judul LIKE ? OR para_pihak LIKE ?)"
            )
            q = f"%{keyword}%"
            params.extend([q, q, q])
        if lokasi:
            conditions.append("lokasi LIKE ?")
            params.append(f"%{lokasi}%")
        if jenis:
            conditions.append("jenis_peradilan LIKE ?")
            params.append(f"%{jenis}%")

        where = " AND ".join(conditions) if conditions else "1=1"

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row

            # Count
            count_row = await conn.execute_fetchall(
                f"SELECT COUNT(*) as cnt FROM putusan WHERE {where}", params
            )
            total = count_row[0][0] if count_row else 0

            # Paginated data
            offset = (page - 1) * per_page
            rows = await conn.execute_fetchall(
                f"""SELECT * FROM putusan WHERE {where}
                    ORDER BY scraped_at DESC
                    LIMIT ? OFFSET ?""",
                params + [per_page, offset],
            )

        results = []
        for row in rows:
            results.append(dict(row))
        return results, total

    async def get_putusan_by_url(self, url: str) -> Optional[Dict]:
        """Fetch a single putusan by its detail URL."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await conn.execute_fetchall(
                "SELECT * FROM putusan WHERE url_detail = ? LIMIT 1", (url,)
            )
            return dict(rows[0]) if rows else None

    # ─── Cache ────────────────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(keyword: str, lokasi: str, jenis: str) -> str:
        raw = f"{keyword}|{lokasi}|{jenis}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def get_cache(
        self, keyword: str, lokasi: str, jenis: str
    ) -> Optional[List[Dict]]:
        """Return cached search results if still valid."""
        key = self._cache_key(keyword, lokasi, jenis)
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await conn.execute_fetchall(
                "SELECT * FROM scrape_cache WHERE cache_key = ? AND expires_at > ?",
                (key, datetime.utcnow().isoformat()),
            )
            if rows:
                return json.loads(rows[0]["data_json"])
        return None

    async def set_cache(
        self,
        keyword: str,
        lokasi: str,
        jenis: str,
        data: List[Dict],
    ) -> None:
        """Store search results in cache."""
        key = self._cache_key(keyword, lokasi, jenis)
        now = datetime.utcnow()
        expires = now + timedelta(seconds=settings.cache_ttl_seconds)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO scrape_cache (cache_key, data_json, total_results, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    data_json     = excluded.data_json,
                    total_results = excluded.total_results,
                    created_at    = excluded.created_at,
                    expires_at    = excluded.expires_at
            """, (key, json.dumps(data), len(data), now.isoformat(), expires.isoformat()))
            await conn.commit()

    async def clear_expired_cache(self) -> int:
        """Remove expired cache entries."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "DELETE FROM scrape_cache WHERE expires_at < ?",
                (datetime.utcnow().isoformat(),),
            )
            await conn.commit()
            return conn.total_changes

    # ─── Search Logs ──────────────────────────────────────────────────────────

    async def log_search(
        self,
        keyword: str,
        lokasi: str,
        jenis: str,
        results_count: int,
        source: str = "live",
    ) -> None:
        """Record a search event for analytics."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO search_logs (keyword, lokasi, jenis_peradilan, results_count, source)
                VALUES (?, ?, ?, ?, ?)
            """, (keyword, lokasi, jenis, results_count, source))
            await conn.commit()


# ─── Singleton ────────────────────────────────────────────────────────────────
db = Database()
