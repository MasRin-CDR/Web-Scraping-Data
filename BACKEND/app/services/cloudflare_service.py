"""
services/cloudflare_service.py — Cloudflare Challenge Detection & Bypass

Service khusus untuk:
- Mendeteksi Cloudflare challenge (Turnstile, IUAM, 403)
- Menganalisa status halaman
- Mengkoordinasi warmup + cookie sync
- Auto-retry saat cf_clearance expired
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.utils.logger import log

# ─── Marker HTML yang menandai Cloudflare Challenge aktif ────────────────────
CF_CHALLENGE_MARKERS = (
    "cf-turnstile",
    "verify you are human",
    "just a moment",
    "checking your browser",
    "cf_chl_opt",
    "cf-challenge-running",
    "challenge-platform",
    "turnstile.cloudflare.com",
    "_cf_chl_f_tk",
    "ray id",
    "please wait",
)

# Marker bahwa halaman sudah berhasil di-load (bukan challenge)
CF_PASS_MARKERS = (
    "direktori",
    "putusan",
    "mahkamah agung",
    "pengadilan",
    "pencarian",
    "search",
)

# Timeout untuk menunggu challenge selesai (maks 5 menit)
MAX_CHALLENGE_WAIT_SEC = 300
# Interval polling saat menunggu challenge selesai
CHALLENGE_POLL_INTERVAL_SEC = 2.0


class CloudflareService:
    """
    Dedicated service untuk menangani semua aspek Cloudflare anti-bot:
    1. Deteksi challenge
    2. Screenshot saat challenge muncul
    3. Koordinasi warmup
    4. Polling status challenge
    5. Cookie validation
    """

    # ─── Challenge Detection ─────────────────────────────────────────────────

    @staticmethod
    def is_challenge_page(html: str) -> bool:
        """
        Deteksi apakah halaman adalah Cloudflare challenge page.
        Menggunakan multiple marker untuk akurasi tinggi.

        Hanya return True jika:
        1. HTML sangat pendek DAN tidak ada content marker, ATAU
        2. Ada CF marker eksplisit
        """
        if not html:
            return True

        lower = html.lower()

        # Cek CF marker eksplisit dulu (paling akurat)
        if any(marker in lower for marker in CF_CHALLENGE_MARKERS):
            return True

        # Halaman benar-benar kosong (< 200 char) tanpa content apapun
        if len(html) < 200 and not any(m in lower for m in CF_PASS_MARKERS):
            return True

        return False

    @staticmethod
    def is_access_granted(html: str) -> bool:
        """
        Deteksi apakah akses sudah berhasil (bukan challenge page).
        """
        if not html:
            return False
        lower = html.lower()
        return any(marker in lower for marker in CF_PASS_MARKERS)

    @classmethod
    def analyze_page(cls, html: str, status_code: Optional[int] = None) -> Dict[str, Any]:
        """
        Analisis menyeluruh kondisi halaman.

        Returns dict dengan:
        - is_challenge: bool
        - is_blocked: bool (403/429)
        - is_ok: bool
        - threat_level: "none" | "soft" | "hard" | "blocked"
        - message: str
        """
        result: Dict[str, Any] = {
            "is_challenge": False,
            "is_blocked": False,
            "is_ok": False,
            "threat_level": "none",
            "message": "Page OK",
            "status_code": status_code,
        }

        # HTTP-level block
        if status_code in (403, 429, 503):
            result["is_blocked"] = True
            result["threat_level"] = "blocked"
            result["message"] = f"HTTP {status_code} — request diblok"

        # HTML-level Cloudflare challenge
        if cls.is_challenge_page(html):
            result["is_challenge"] = True
            result["threat_level"] = "hard" if status_code == 403 else "soft"
            result["message"] = "Cloudflare challenge terdeteksi"
            return result

        # Akses berhasil jika:
        # - Ada pass marker di HTML, ATAU
        # - Status 200 dan tidak ada challenge
        if cls.is_access_granted(html) or (status_code == 200 and not result["is_challenge"]):
            result["is_ok"] = True
            result["threat_level"] = "none"
            result["message"] = "Akses berhasil"

        return result

    # ─── Screenshot on Challenge ─────────────────────────────────────────────

    @staticmethod
    async def screenshot_challenge(page, screenshot_dir) -> Optional[str]:
        """
        Ambil screenshot saat challenge muncul untuk debugging.
        Simpan ke screenshots/ dengan timestamp.
        Returns path screenshot atau None jika gagal.
        """
        from pathlib import Path
        try:
            shots_dir = Path(screenshot_dir)
            shots_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = shots_dir / f"cf_challenge_{ts}.png"
            await page.screenshot(path=str(path), full_page=False)
            log.warning("📸 Screenshot challenge disimpan: {}", path)
            return str(path)
        except Exception as exc:
            log.debug("Screenshot gagal: {}", exc)
            return None

    # ─── Challenge Wait Loop ─────────────────────────────────────────────────

    @staticmethod
    async def wait_for_challenge_solved(
        page,
        timeout_sec: float = MAX_CHALLENGE_WAIT_SEC,
        poll_interval: float = CHALLENGE_POLL_INTERVAL_SEC,
    ) -> Tuple[bool, str]:
        """
        Polling loop — tunggu sampai user selesaikan Cloudflare challenge.
        Dipanggil saat headless=False dan user perlu manual solve.

        Returns: (solved: bool, final_html: str)
        """
        start = asyncio.get_event_loop().time()
        log.info(
            "⏳ Menunggu user selesaikan Cloudflare challenge... (maks {:.0f} detik)",
            timeout_sec,
        )

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > timeout_sec:
                log.error("⏰ Timeout! Challenge tidak diselesaikan dalam {:.0f} detik", timeout_sec)
                return False, ""

            await asyncio.sleep(poll_interval)

            try:
                html = await page.content()
                if not CloudflareService.is_challenge_page(html):
                    log.success("✅ Cloudflare challenge berhasil diselesaikan!")
                    return True, html
                log.debug("⏳ Challenge masih aktif ({:.0f}s / {:.0f}s)...", elapsed, timeout_sec)
            except Exception as exc:
                log.debug("Poll error: {}", exc)

    # ─── HTTP Header Builder ──────────────────────────────────────────────────

    @staticmethod
    def build_stealth_headers(
        user_agent: str,
        referer: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Bangun header HTTP yang realistis untuk menghindari deteksi bot.
        """
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        if referer:
            headers["Referer"] = referer
        if origin:
            headers["Origin"] = origin
        return headers


# ─── Singleton ────────────────────────────────────────────────────────────────
cloudflare_service = CloudflareService()
