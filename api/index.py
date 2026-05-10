from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI(
    title="Direktori Putusan Mahkamah Agung - Vercel API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_lokasi() -> list[str]:
    frontend_js = Path(__file__).resolve().parents[1] / "FRONTEND" / "app.js"
    fallback = ["MAHKAMAH AGUNG", "PENGADILAN PAJAK"]
    try:
        text = frontend_js.read_text(encoding="utf-8")
        match = re.search(r"const\s+LOKASI_LIST\s*=\s*\[(.*?)\];", text, re.S)
        if not match:
            return fallback
        return sorted(dict.fromkeys(re.findall(r"'([^']+)'", match.group(1))), key=str.casefold)
    except Exception:
        return fallback


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.0.0",
        "browser_ready": False,
        "database_ready": False,
        "cf_clearance": False,
        "runtime": "vercel",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/lokasi")
async def lokasi() -> dict[str, Any]:
    data = _load_lokasi()
    return {"data": data, "total": len(data)}


@app.get("/api/warmup-status")
async def warmup_status() -> dict[str, Any]:
    return {
        "status": "static",
        "cf_clearance": False,
        "message": "Mode production Vercel aktif. Scraping Playwright berjalan di backend lokal/Docker.",
    }


@app.post("/api/warmup")
async def warmup() -> dict[str, Any]:
    return {
        "status": "static",
        "message": "Warm-up Cloudflare hanya tersedia saat menjalankan backend FastAPI lokal/Docker.",
        "direct_access": False,
    }


@app.post("/api/search")
async def search(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "total": 0,
        "page": int(payload.get("page") or 1),
        "per_page": int(payload.get("per_page") or 20),
        "total_pages": 0,
        "data": [],
        "source": "vercel-static",
        "scraped_at": datetime.utcnow().isoformat(),
        "message": "API production aktif. Untuk scraping live, jalankan backend FastAPI lokal/Docker karena membutuhkan Chromium Playwright dan sesi Cloudflare.",
    }


@app.post("/api/detail")
async def detail(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "message": "Detail putusan live tersedia saat backend FastAPI lokal/Docker aktif.",
    }


@app.get("/api/download-pdf")
async def download_pdf(url: str = Query("")) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Download PDF live tersedia saat backend FastAPI lokal/Docker aktif.",
            "url": url,
        },
    )
