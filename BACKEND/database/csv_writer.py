"""
database/csv_writer.py - Async CSV Export
Writes PutusanRecord objects to CSV incrementally.
"""

from __future__ import annotations

import csv
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List

import aiofiles

from config import settings
from database.models import PutusanRecord
from utils.logger import log

# Column order for the CSV
CSV_COLUMNS = [
    "judul",
    "nomor_putusan",
    "tanggal_putusan",
    "tanggal_register",
    "url_detail",
    "url_pdf",
    "klasifikasi",
    "sub_klasifikasi",
    "jenis_lembaga",
    "lembaga_peradilan",
    "tingkat_proses",
    "tahun",
    "para_pihak",
    "amar_putusan",
    "scraped_at",
    "source_page",
]


class CSVWriter:
    """
    Async CSV writer that appends records to a timestamped CSV file.
    Thread-safe via asyncio Lock.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._dir = output_dir or settings.csv_output_dir
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._path = self._dir / f"putusan_{timestamp}.csv"
        self._lock = asyncio.Lock()
        self._initialized = False
        self._total_written = 0

    @property
    def path(self) -> Path:
        return self._path

    async def _write_header(self) -> None:
        """Write the CSV header row."""
        async with aiofiles.open(self._path, mode="w", encoding="utf-8", newline="") as f:
            await f.write(",".join(CSV_COLUMNS) + "\n")
        log.info("CSV file created: {}", self._path)

    def _escape(self, value: str) -> str:
        """Escape a CSV field value."""
        if '"' in value or "," in value or "\n" in value:
            return '"' + value.replace('"', '""') + '"'
        return value

    async def write_records(self, records: List[PutusanRecord]) -> int:
        """
        Append a list of records to the CSV.
        Returns number of rows written.
        """
        if not records:
            return 0

        async with self._lock:
            if not self._initialized:
                await self._write_header()
                self._initialized = True

            lines: list[str] = []
            for record in records:
                row = record.to_csv_row()
                fields = [self._escape(str(row.get(col, ""))) for col in CSV_COLUMNS]
                lines.append(",".join(fields))

            async with aiofiles.open(self._path, mode="a", encoding="utf-8", newline="") as f:
                await f.write("\n".join(lines) + "\n")

            count = len(records)
            self._total_written += count
            log.debug("CSV | wrote {} rows | total={}", count, self._total_written)
            return count

    async def write_record(self, record: PutusanRecord) -> bool:
        """Convenience method to write a single record."""
        written = await self.write_records([record])
        return written > 0

    def summary(self) -> str:
        return f"CSV output: {self._path} | total rows: {self._total_written}"
