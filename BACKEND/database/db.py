"""
database/db.py - Async PostgreSQL Database Layer
Uses asyncpg for high-performance async operations.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncpg

from config import settings
from database.models import PutusanRecord
from utils.logger import log

# ─── DDL ─────────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS putusan (
    id              BIGSERIAL PRIMARY KEY,
    judul           TEXT        NOT NULL,
    nomor_putusan   TEXT,
    tanggal_putusan DATE,
    tanggal_register DATE,
    url_detail      TEXT,
    url_pdf         TEXT,
    klasifikasi     TEXT,
    sub_klasifikasi TEXT,
    jenis_lembaga   TEXT,
    lembaga_peradilan TEXT,
    tingkat_proses  TEXT,
    tahun           TEXT,
    para_pihak      TEXT,
    amar_putusan    TEXT,
    metadata_extra  JSONB       DEFAULT '{}',
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_page     INTEGER     DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_putusan_nomor
    ON putusan (nomor_putusan)
    WHERE nomor_putusan IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_putusan_tanggal
    ON putusan (tanggal_putusan DESC);

CREATE INDEX IF NOT EXISTS idx_putusan_scraped
    ON putusan (scraped_at DESC);
"""

INSERT_SQL = """
INSERT INTO putusan (
    judul, nomor_putusan, tanggal_putusan, tanggal_register,
    url_detail, url_pdf,
    klasifikasi, sub_klasifikasi, jenis_lembaga, lembaga_peradilan,
    tingkat_proses, tahun, para_pihak, amar_putusan,
    metadata_extra, scraped_at, source_page
) VALUES (
    $1, $2, $3, $4, $5, $6,
    $7, $8, $9, $10, $11, $12, $13, $14,
    $15, $16, $17
)
ON CONFLICT (nomor_putusan) DO UPDATE SET
    judul           = EXCLUDED.judul,
    tanggal_putusan = EXCLUDED.tanggal_putusan,
    url_pdf         = COALESCE(EXCLUDED.url_pdf, putusan.url_pdf),
    metadata_extra  = EXCLUDED.metadata_extra,
    scraped_at      = EXCLUDED.scraped_at
RETURNING id;
"""


class Database:
    """Async PostgreSQL connection pool wrapper."""

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create the connection pool and ensure schema exists."""
        log.info("Connecting to PostgreSQL at {}:{}/{}", 
                 settings.db_host, settings.db_port, settings.db_name)
        try:
            self._pool = await asyncpg.create_pool(
                **settings.db_dsn_asyncpg,
                min_size=2,
                max_size=10,
                command_timeout=30,
                statement_cache_size=0,  # avoids pgBouncer issues
            )
            await self._init_schema()
            log.success("PostgreSQL connected | pool_size=2-10")
        except Exception as exc:
            log.error("Failed to connect to PostgreSQL: {}", exc)
            raise

    async def disconnect(self) -> None:
        """Gracefully close the connection pool."""
        if self._pool:
            await self._pool.close()
            log.info("PostgreSQL pool closed")

    async def _init_schema(self) -> None:
        """Run DDL statements to ensure tables exist."""
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
        log.debug("Database schema initialized")

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Context manager for acquiring a pool connection."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        async with self._pool.acquire() as conn:
            yield conn

    # ─── Write Operations ────────────────────────────────────────────────────

    async def upsert_putusan(self, record: PutusanRecord) -> Optional[int]:
        """
        Insert or update a single PutusanRecord.
        Returns the database row ID on success, None on failure.
        """
        meta = record.metadata
        try:
            async with self.acquire() as conn:
                row_id = await conn.fetchval(
                    INSERT_SQL,
                    record.judul,
                    record.nomor_putusan,
                    record.tanggal_putusan.date() if record.tanggal_putusan else None,
                    record.tanggal_register.date() if record.tanggal_register else None,
                    record.url_detail,
                    record.url_pdf,
                    meta.klasifikasi,
                    meta.sub_klasifikasi,
                    meta.jenis_lembaga_peradilan,
                    meta.lembaga_peradilan,
                    meta.tingkat_proses,
                    meta.tahun,
                    meta.para_pihak,
                    meta.amar_putusan,
                    json.dumps(meta.extra),
                    record.scraped_at,
                    record.source_page,
                )
                return row_id
        except asyncpg.UniqueViolationError:
            log.debug("Duplicate nomor_putusan skipped: {}", record.nomor_putusan)
            return None
        except Exception as exc:
            log.error("DB upsert failed for '{}': {}", record.judul[:60], exc)
            return None

    async def bulk_upsert(self, records: list[PutusanRecord]) -> int:
        """
        Upsert a batch of records.
        Returns count of successfully inserted/updated rows.
        """
        success = 0
        for record in records:
            row_id = await self.upsert_putusan(record)
            if row_id is not None:
                success += 1
        log.info("Bulk upsert complete | inserted/updated={}/{}", success, len(records))
        return success

    # ─── Read Operations ─────────────────────────────────────────────────────

    async def get_total_count(self) -> int:
        """Return total number of scraped records."""
        async with self.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM putusan")

    async def get_scraped_nomors(self) -> set[str]:
        """Return set of already-scraped nomor_putusan for deduplication."""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                "SELECT nomor_putusan FROM putusan WHERE nomor_putusan IS NOT NULL"
            )
            return {row["nomor_putusan"] for row in rows}


# ─── Singleton ───────────────────────────────────────────────────────────────
db = Database()
