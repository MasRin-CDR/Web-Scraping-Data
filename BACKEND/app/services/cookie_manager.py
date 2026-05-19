"""
services/cookie_manager.py — Persistent Cookie Manager

Mengelola penyimpanan dan pemulihan cookie Cloudflare (cf_clearance) ke/dari JSON.
Cookie disimpan di cookies/session.json dan di-load ulang saat startup.
Auto-refresh jika cookie mendekati kedaluwarsa.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

from app.utils.logger import log

# ─── Lokasi file cookie ────────────────────────────────────────────────────────
# BACKEND/cookies/session.json
COOKIES_DIR = Path(__file__).resolve().parent.parent.parent / "cookies"
COOKIES_FILE = COOKIES_DIR / "session.json"

# Cookie Cloudflare yang paling penting
CF_CLEARANCE_NAME = "cf_clearance"

# Anggap cookie butuh refresh jika sisa TTL < 10 menit
REFRESH_THRESHOLD_SEC = 600


class CookieManager:
    """
    Async cookie manager yang menyimpan cookie ke disk (JSON) dan
    me-load-nya kembali saat startup agar session Cloudflare tetap valid.
    """

    def __init__(self, cookie_file: Optional[Path] = None) -> None:
        self._file = cookie_file or COOKIES_FILE
        self._cookies: List[Dict[str, Any]] = []
        self._last_saved: Optional[datetime] = None

    # ─── Load ─────────────────────────────────────────────────────────────────

    async def load(self) -> List[Dict[str, Any]]:
        """
        Baca cookies dari file JSON.
        Return list kosong jika file tidak ada atau corrupt.
        """
        if not self._file.exists():
            log.info("Cookie file tidak ditemukan — session baru akan dibuat: {}", self._file)
            return []

        try:
            async with aiofiles.open(self._file, "r", encoding="utf-8") as f:
                content = await f.read()

            data = json.loads(content)
            self._cookies = data if isinstance(data, list) else []
            cf = self._get_cf_clearance()
            if cf:
                log.success(
                    "Cookie dimuat: {} cookies | cf_clearance ada (expires: {})",
                    len(self._cookies),
                    cf.get("expires", "unknown"),
                )
            else:
                log.warning(
                    "Cookie dimuat: {} cookies | cf_clearance TIDAK ADA — warmup diperlukan",
                    len(self._cookies),
                )
            return self._cookies

        except (json.JSONDecodeError, OSError) as exc:
            log.error("Gagal membaca cookie file: {}", exc)
            self._cookies = []
            return []

    # ─── Save ─────────────────────────────────────────────────────────────────

    async def save(self, cookies: List[Dict[str, Any]]) -> None:
        """
        Simpan cookies ke JSON file.
        Otomatis membuat direktori jika belum ada.
        """
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._cookies = cookies

            async with aiofiles.open(self._file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(cookies, indent=2, ensure_ascii=False))

            self._last_saved = datetime.now(tz=timezone.utc)
            cf = self._get_cf_clearance()
            log.success(
                "Cookie disimpan: {} cookies | cf_clearance: {} | file: {}",
                len(cookies),
                "✅ ADA" if cf else "❌ TIDAK ADA",
                self._file,
            )
        except OSError as exc:
            log.error("Gagal menyimpan cookie: {}", exc)

    # ─── Cookie Access ────────────────────────────────────────────────────────

    def get_all(self) -> List[Dict[str, Any]]:
        """Return semua cookie yang tersimpan di memori."""
        return list(self._cookies)

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Cari cookie berdasarkan nama (case-sensitive)."""
        return next((c for c in self._cookies if c.get("name") == name), None)

    def has_cf_clearance(self) -> bool:
        """Cek apakah cf_clearance ada dan belum expired."""
        cf = self._get_cf_clearance()
        if not cf:
            return False
        return not self._is_expired(cf)

    def needs_refresh(self) -> bool:
        """
        Return True jika cf_clearance akan kedaluwarsa dalam waktu dekat
        atau tidak ada sama sekali.
        """
        cf = self._get_cf_clearance()
        if not cf:
            return True
        expires = cf.get("expires")
        if not expires or expires == -1:
            # Session cookie — selalu valid selama browser hidup
            return False
        try:
            # expires bisa berupa Unix timestamp (float/int)
            exp_dt = datetime.fromtimestamp(float(expires), tz=timezone.utc)
            remaining = (exp_dt - datetime.now(tz=timezone.utc)).total_seconds()
            return remaining < REFRESH_THRESHOLD_SEC
        except (TypeError, ValueError, OSError):
            return True

    def cf_clearance_value(self) -> Optional[str]:
        """Return nilai cf_clearance cookie jika ada."""
        cf = self._get_cf_clearance()
        return cf.get("value") if cf else None

    def cf_expires_at(self) -> Optional[str]:
        """Return waktu kedaluwarsa cf_clearance sebagai ISO string."""
        cf = self._get_cf_clearance()
        if not cf:
            return None
        expires = cf.get("expires")
        if not expires or expires == -1:
            return "session (browser-lifetime)"
        try:
            exp_dt = datetime.fromtimestamp(float(expires), tz=timezone.utc)
            return exp_dt.isoformat()
        except (TypeError, ValueError, OSError):
            return str(expires)

    # ─── Delete ───────────────────────────────────────────────────────────────

    async def clear(self) -> None:
        """Hapus semua cookies (dari memori dan disk)."""
        self._cookies = []
        try:
            if self._file.exists():
                self._file.unlink()
                log.info("Cookie file dihapus: {}", self._file)
        except OSError as exc:
            log.warning("Gagal hapus cookie file: {}", exc)

    # ─── Sync dari Browser Context ────────────────────────────────────────────

    async def sync_from_context(self, context) -> None:
        """
        Ambil cookies dari Playwright BrowserContext dan simpan ke disk.
        Dipanggil setelah warmup berhasil.
        """
        try:
            cookies = await context.cookies()
            await self.save(cookies)
        except Exception as exc:
            log.error("Gagal sync cookie dari browser: {}", exc)

    async def apply_to_context(self, context) -> bool:
        """
        Terapkan cookies yang tersimpan ke Playwright BrowserContext.
        Return True jika ada cf_clearance yang diterapkan.
        """
        if not self._cookies:
            await self.load()

        if not self._cookies:
            log.debug("Tidak ada cookie yang perlu diterapkan")
            return False

        try:
            await context.add_cookies(self._cookies)
            has_cf = self.has_cf_clearance()
            log.info(
                "Cookie diterapkan ke browser context: {} cookies | cf_clearance: {}",
                len(self._cookies),
                "✅" if has_cf else "❌",
            )
            return has_cf
        except Exception as exc:
            log.error("Gagal menerapkan cookie ke context: {}", exc)
            return False

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _get_cf_clearance(self) -> Optional[Dict[str, Any]]:
        return next((c for c in self._cookies if c.get("name") == CF_CLEARANCE_NAME), None)

    @staticmethod
    def _is_expired(cookie: Dict[str, Any]) -> bool:
        expires = cookie.get("expires")
        if not expires or expires == -1:
            return False  # session cookie
        try:
            exp_dt = datetime.fromtimestamp(float(expires), tz=timezone.utc)
            return datetime.now(tz=timezone.utc) > exp_dt
        except (TypeError, ValueError, OSError):
            return False

    # ─── Status ───────────────────────────────────────────────────────────────

    def status_dict(self) -> Dict[str, Any]:
        """Return status cookie dalam bentuk dict untuk endpoint API."""
        return {
            "has_cf_clearance": self.has_cf_clearance(),
            "needs_refresh": self.needs_refresh(),
            "cf_clearance_value": self.cf_clearance_value(),
            "cf_expires_at": self.cf_expires_at(),
            "total_cookies": len(self._cookies),
            "last_saved": self._last_saved.isoformat() if self._last_saved else None,
            "cookie_file": str(self._file),
        }


# ─── Singleton ────────────────────────────────────────────────────────────────
cookie_manager = CookieManager()
