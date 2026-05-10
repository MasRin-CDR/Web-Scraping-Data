"""
database/models.py - Pydantic Data Models
Defines the schema for scraped putusan (verdict) records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PutusanMetadata(BaseModel):
    """Flexible metadata container for extra key-value pairs."""

    klasifikasi: Optional[str] = None
    sub_klasifikasi: Optional[str] = None
    jenis_lembaga_peradilan: Optional[str] = None
    lembaga_peradilan: Optional[str] = None
    tingkat_proses: Optional[str] = None
    tahun: Optional[str] = None
    para_pihak: Optional[str] = None
    amar_putusan: Optional[str] = None
    catatan_amar: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class PutusanRecord(BaseModel):
    """
    Represents a single putusan (court verdict) scraped from
    Mahkamah Agung's direktori.
    """

    # ── Core fields ───────────────────────────────────────────────────────────
    judul: str = Field(description="Title / case title of the verdict")
    nomor_putusan: Optional[str] = Field(
        default=None, description="Case registration number"
    )
    tanggal_putusan: Optional[datetime] = Field(
        default=None, description="Date of verdict"
    )
    tanggal_register: Optional[datetime] = Field(
        default=None, description="Date of registration"
    )

    # ── Links ─────────────────────────────────────────────────────────────────
    url_detail: Optional[str] = Field(
        default=None, description="URL to verdict detail page"
    )
    url_pdf: Optional[str] = Field(
        default=None, description="Direct PDF download URL"
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata: PutusanMetadata = Field(default_factory=PutusanMetadata)

    # ── Audit ─────────────────────────────────────────────────────────────────
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    source_page: int = Field(default=1, description="Pagination page number")
    raw_html: Optional[str] = Field(
        default=None, description="Raw HTML of the card (debug only)"
    )

    @field_validator("judul", mode="before")
    @classmethod
    def clean_judul(cls, v: Any) -> str:
        if not v:
            raise ValueError("judul cannot be empty")
        import re
        return re.sub(r"\s+", " ", str(v)).strip()

    def to_csv_row(self) -> dict[str, Any]:
        """Flatten record for CSV export."""
        meta = self.metadata
        return {
            "judul": self.judul,
            "nomor_putusan": self.nomor_putusan or "",
            "tanggal_putusan": (
                self.tanggal_putusan.strftime("%Y-%m-%d")
                if self.tanggal_putusan
                else ""
            ),
            "tanggal_register": (
                self.tanggal_register.strftime("%Y-%m-%d")
                if self.tanggal_register
                else ""
            ),
            "url_detail": self.url_detail or "",
            "url_pdf": self.url_pdf or "",
            "klasifikasi": meta.klasifikasi or "",
            "sub_klasifikasi": meta.sub_klasifikasi or "",
            "jenis_lembaga": meta.jenis_lembaga_peradilan or "",
            "lembaga_peradilan": meta.lembaga_peradilan or "",
            "tingkat_proses": meta.tingkat_proses or "",
            "tahun": meta.tahun or "",
            "para_pihak": meta.para_pihak or "",
            "amar_putusan": meta.amar_putusan or "",
            "scraped_at": self.scraped_at.strftime("%Y-%m-%d %H:%M:%S"),
            "source_page": self.source_page,
        }

    class Config:
        arbitrary_types_allowed = True
