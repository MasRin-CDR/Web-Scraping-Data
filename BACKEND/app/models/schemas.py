"""
models/schemas.py — Pydantic Request / Response Schemas
All API contracts are defined here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─── Request Schemas ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """Payload sent by the frontend search form."""
    keyword: str = Field(default="", description="Free-text search keyword")
    lokasi: str = Field(default="", description="Court location filter")
    jenis_peradilan: str = Field(default="", description="Court type filter")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Results per page")


class DetailRequest(BaseModel):
    """Request for putusan detail page."""
    url: str = Field(description="Detail page URL to scrape")


# ─── Data Item Schemas ────────────────────────────────────────────────────────

class PutusanItem(BaseModel):
    """Single putusan record in search results."""
    id: Optional[int] = None
    nomor_perkara: str = ""
    tahun: Optional[str] = None
    lokasi: str = ""
    jenis_peradilan: str = ""
    judul: str = ""
    tanggal_putusan: Optional[str] = None
    status: str = ""
    url_detail: Optional[str] = None
    url_pdf: Optional[str] = None


class PutusanDetail(BaseModel):
    """Full detail of a single putusan."""
    nomor_perkara: str = ""
    tahun: Optional[str] = None
    lokasi: str = ""
    jenis_peradilan: str = ""
    judul: str = ""
    tanggal_putusan: Optional[str] = None
    tanggal_register: Optional[str] = None
    status: str = ""
    hakim: Optional[str] = None
    panitera: Optional[str] = None
    amar_putusan: Optional[str] = None
    klasifikasi: Optional[str] = None
    sub_klasifikasi: Optional[str] = None
    tingkat_proses: Optional[str] = None
    url_detail: Optional[str] = None
    url_pdf: Optional[str] = None
    para_pihak: Optional[str] = None
    catatan: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── Response Schemas ─────────────────────────────────────────────────────────

class SearchResponse(BaseModel):
    """Response returned by /api/search."""
    success: bool = True
    total: int = 0
    page: int = 1
    per_page: int = 20
    total_pages: int = 0
    data: List[PutusanItem] = Field(default_factory=list)
    source: str = "live"           # "live" | "cache" | "database"
    scraped_at: Optional[str] = None
    message: str = ""


class DetailResponse(BaseModel):
    """Response returned by /api/detail."""
    success: bool = True
    data: Optional[PutusanDetail] = None
    message: str = ""


class HealthResponse(BaseModel):
    """Response returned by /api/health."""
    status: str = "ok"
    version: str = "1.0.0"
    browser_ready: bool = False
    database_ready: bool = False
    cf_clearance: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    message: str = ""
    detail: Optional[str] = None
