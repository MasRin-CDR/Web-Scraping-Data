# 🏛️ Mahkamah Agung Scraper — Backend v2.0

> **Production-ready** FastAPI + Playwright scraping backend dengan **Cloudflare Challenge bypass** otomatis, persistent session, dan anti-detection lengkap.

---

## 🎯 Fitur Utama

| Fitur | Status |
|---|---|
| Cloudflare Turnstile Bypass | ✅ |
| Persistent `cf_clearance` Cookie | ✅ |
| Cookie JSON Storage (disk) | ✅ |
| Auto Cookie Load saat Startup | ✅ |
| Stealth Browser Fingerprint (12 teknik) | ✅ |
| Human Simulation (scroll, mouse, delay) | ✅ |
| Auto Retry + Exponential Backoff | ✅ |
| Screenshot saat Challenge | ✅ |
| Modular Routes (warmup/search/detail) | ✅ |
| SQLite Cache (TTL 1 jam) | ✅ |
| Async Semaphore (rate limiting) | ✅ |
| Loguru Structured Logging | ✅ |
| CORS Middleware | ✅ |
| Health Check + Browser Status | ✅ |

---

## 🗂️ Struktur Project

```
BACKEND/
│
├── app/
│   ├── main.py                    ← FastAPI app + lifespan
│   ├── config.py                  ← Semua settings via pydantic-settings
│   │
│   ├── routes/                    ← Modular route handlers
│   │   ├── __init__.py
│   │   ├── warmup.py              ← /api/warmup, /api/warmup-status, /api/browser-status
│   │   ├── search.py              ← /api/search, /api/lokasi
│   │   └── detail.py             ← /api/detail, /api/download-pdf
│   │
│   ├── services/                  ← Business logic layer
│   │   ├── browser_manager.py     ← Orkestrasi warmup + cookie sync
│   │   ├── cloudflare_service.py  ← CF detection + analysis
│   │   ├── cookie_manager.py      ← Persistent JSON cookie storage
│   │   ├── scraper_service.py     ← Async scraping + retry guard
│   │   └── search_service.py      ← Cache → scrape → DB flow
│   │
│   ├── scraper/                   ← Low-level browser automation
│   │   ├── browser.py             ← StealthBrowser (Playwright context)
│   │   ├── engine.py              ← ScrapingEngine (navigate + extract)
│   │   └── parser.py              ← BeautifulSoup HTML parser
│   │
│   ├── models/
│   │   ├── database.py            ← SQLite async layer (aiosqlite)
│   │   └── schemas.py             ← Pydantic request/response schemas
│   │
│   ├── utils/
│   │   ├── stealth.py             ← JS injection + fingerprint spoofing
│   │   ├── helpers.py             ← URL utils, date parsing, text cleaning
│   │   └── logger.py              ← Loguru setup (console + file)
│   │
│   └── api/
│       └── routes.py              ← Legacy routes (backward compat)
│
├── cookies/
│   └── session.json               ← cf_clearance cookie (auto-generated)
│
├── data/
│   ├── mahkamah.db               ← SQLite database
│   ├── browser_profile/          ← Chromium persistent profile
│   └── screenshots/              ← Challenge screenshots (debug)
│
├── logs/
│   ├── mahkamah.log              ← Semua log (rotating 10MB)
│   └── mahkamah_errors.log       ← Error-only log
│
├── .env                          ← Environment variables (buat dari .env.example)
├── requirements.txt              ← Python dependencies
└── main.py                       ← CLI launcher
```

---

## 🚀 Cara Install

### 1. Prerequisites

```bash
# Python 3.11+
python --version  # harus 3.11 atau lebih baru

# Node.js tidak diperlukan
```

### 2. Install Dependencies

```bash
# Masuk ke direktori BACKEND
cd BACKEND

# Buat virtual environment
python -m venv .venv

# Aktifkan venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Install Playwright Chromium

```bash
# Install Chromium browser untuk Playwright
playwright install chromium

# Jika di Linux server, install system dependencies:
playwright install-deps chromium
```

### 4. Setup Environment

```bash
# Copy template .env (sudah ada di BACKEND/.env)
# Edit sesuai kebutuhan:
```

**Untuk development (manual Turnstile solve):**
```env
HEADLESS=false    ← Jendela Chrome muncul untuk solve Turnstile
DEBUG=true
```

**Untuk production/Docker:**
```env
HEADLESS=true     ← Background mode
DEBUG=false
```

---

## ▶️ Cara Run

### Development Mode

```bash
cd BACKEND

# Jalankan dengan auto-reload
python main.py

# ATAU dengan uvicorn langsung:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
cd BACKEND

# Jalankan tanpa reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# CATATAN: Gunakan workers=1 karena browser adalah singleton stateful
# Multi-worker akan menyebabkan konflik browser context
```

Server akan berjalan di: **http://localhost:8000**  
API Docs (Swagger): **http://localhost:8000/docs**

---

## 🔥 Cara Warmup (Bypass Cloudflare)

Warmup harus dilakukan **sekali** sebelum bisa scraping.
Cookie `cf_clearance` akan disimpan dan digunakan otomatis untuk semua request berikutnya.

### Langkah Warmup

#### Step 1 — Mulai Warmup

```bash
curl -X POST http://localhost:8000/api/warmup
```

**Response jika tidak ada challenge:**
```json
{
  "success": true,
  "status": "solved",
  "message": "✅ Cloudflare bypass berhasil! Session siap digunakan.",
  "cf_clearance": true
}
```

**Response jika ada Turnstile challenge:**
```json
{
  "success": false,
  "status": "challenge",
  "message": "⚠️ Cloudflare Turnstile terdeteksi! Selesaikan verifikasi di jendela Chromium.",
  "cf_clearance": false,
  "screenshot": "/path/to/screenshot.png"
}
```

→ Jika `status = "challenge"` dan `HEADLESS=false`:  
   **Selesaikan verifikasi di jendela Chromium yang muncul**, lalu lanjutkan ke Step 2.

#### Step 2 — Poll Status (jika ada challenge)

```bash
# Poll setiap 2-3 detik sampai status = "solved"
curl http://localhost:8000/api/warmup-status
```

**Response setelah solved:**
```json
{
  "status": "solved",
  "success": true,
  "cf_clearance": true,
  "cookie_info": {
    "has_cf_clearance": true,
    "cf_expires_at": "2026-06-18T09:30:00+00:00",
    "total_cookies": 8
  }
}
```

#### Session Persisten

Cookie `cf_clearance` **otomatis tersimpan** ke `cookies/session.json`.  
Saat backend **restart**, cookie di-load otomatis → tidak perlu warmup ulang (selama belum expired).

---

## 🔍 Cara Test API

### Health Check

```bash
curl http://localhost:8000/api/health
```

### Search Putusan

```bash
# GET request
curl "http://localhost:8000/api/search?q=korupsi&page=1&per_page=10"

# Dengan filter lokasi
curl "http://localhost:8000/api/search?q=perdata&lokasi=MAHKAMAH+AGUNG&jenis=Perdata"

# POST request
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "korupsi", "lokasi": "", "jenis_peradilan": "", "page": 1, "per_page": 20}'
```

**Response:**
```json
{
  "success": true,
  "total": 150,
  "page": 1,
  "per_page": 20,
  "total_pages": 8,
  "source": "live",
  "data": [
    {
      "nomor_perkara": "123/Pid.B/2024/PN.Jkt.Pst",
      "judul": "Putusan Pidana Korupsi",
      "tanggal_putusan": "2024-03-15",
      "lokasi": "PENGADILAN NEGERI JAKARTA PUSAT",
      "url_detail": "https://putusan3.mahkamahagung.go.id/...",
      "url_pdf": "https://putusan3.mahkamahagung.go.id/..."
    }
  ],
  "message": "150 hasil ditemukan"
}
```

### Detail Putusan

```bash
# GET
curl "http://localhost:8000/api/detail?url=https://putusan3.mahkamahagung.go.id/putusan/..."

# POST
curl -X POST http://localhost:8000/api/detail \
  -H "Content-Type: application/json" \
  -d '{"url": "https://putusan3.mahkamahagung.go.id/putusan/..."}'
```

### Download PDF

```bash
curl -O "http://localhost:8000/api/download-pdf?url=https://putusan3.mahkamahagung.go.id/...pdf"
```

### Browser Status

```bash
curl http://localhost:8000/api/browser-status
```

**Response:**
```json
{
  "success": true,
  "data": {
    "browser_ready": true,
    "warmup_status": "solved",
    "cf_clearance_in_browser": true,
    "session_valid": true,
    "needs_warmup": false,
    "headless": false,
    "open_pages": 0,
    "started_at": "2026-05-19T09:00:00+00:00",
    "last_warmup": "2026-05-19T09:01:30+00:00",
    "cookie": {
      "has_cf_clearance": true,
      "cf_expires_at": "2026-06-18T09:00:00+00:00",
      "total_cookies": 8
    }
  }
}
```

---

## 📡 API Reference

### Warmup Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/warmup` | Mulai Cloudflare bypass |
| `GET` | `/api/warmup-status` | Poll status warmup |
| `POST` | `/api/warmup/reset` | Reset warmup state |
| `GET` | `/api/browser-status` | Status detail browser + session |
| `GET` | `/api/health` | Health check |

### Cookie Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/api/cookie-status` | Status cookie di disk |
| `POST` | `/api/cookies/sync` | Sync cookie browser → disk |
| `DELETE` | `/api/cookies` | Hapus semua cookie (force re-warmup) |
| `GET` | `/api/screenshot` | Screenshot challenge terakhir |

### Scraping Endpoints

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/api/search?q=...` | Search putusan |
| `POST` | `/api/search` | Search (POST body) |
| `GET` | `/api/detail?url=...` | Detail putusan |
| `POST` | `/api/detail` | Detail (POST body) |
| `GET` | `/api/download-pdf?url=...` | Download PDF |
| `GET` | `/api/lokasi` | List lokasi pengadilan |

---

## 🛡️ Anti-Detection Strategy

### Browser Fingerprint Spoofing
- `navigator.webdriver` → `undefined`
- `navigator.plugins` → realistic Chrome PDF plugins (5 entries)
- `navigator.languages` → `['id-ID', 'id', 'en-US', 'en']`
- `navigator.permissions.query` → patched untuk Notification
- `chrome.runtime` → full object injection
- **WebGL Vendor/Renderer** → Intel GPU (bukan LLVMpipe headless)
- `navigator.hardwareConcurrency` → 8 cores
- `navigator.deviceMemory` → 8 GB
- `window.outerHeight/outerWidth` → bukan 0 (seperti headless biasanya)

### Request-Level Evasion
- Random User-Agent dari pool 9 browser
- Random viewport (1280×800 → 1920×1080)
- Random timezone (Jakarta/Makassar/Jayapura)
- Realistic HTTP headers (Accept, Accept-Encoding, Sec-Fetch-*)
- Random human delays (2–5 detik antar request)
- Smooth scroll simulation
- Realistic mouse movement (curved path)

### Session Management
- Persistent Chromium profile (simpan cookies, localStorage)
- Cookie sync ke `cookies/session.json` (backup disk)
- Auto-load cookies saat startup
- CF challenge detection multi-marker (10 pattern)

---

## 🔄 Startup Flow

```
Backend Start
    │
    ├─ Init SQLite Database
    │
    ├─ Launch Chromium (stealth, persistent profile)
    │
    ├─ Load cookies/session.json
    │   │
    │   ├─ cf_clearance ADA + valid?
    │   │   └─ Apply ke browser context → SIAP SCRAPING ✅
    │   │
    │   └─ cf_clearance TIDAK ADA / expired?
    │       └─ Log warning → perlu warmup ⚠️
    │
    └─ Server ready at :8000
```

---

## 🔧 Troubleshooting

### ❌ HTTP 403 saat scraping
```bash
# Warmup ulang
curl -X POST http://localhost:8000/api/warmup

# Cek status
curl http://localhost:8000/api/warmup-status
```

### ❌ Challenge tidak bisa di-solve (headless=true)
```env
# Ubah di .env:
HEADLESS=false
```
Restart server → jendela Chromium akan muncul → solve Turnstile → status berubah ke "solved".

### ❌ Cookie expired
```bash
# Hapus cookie lama dan warmup ulang
curl -X DELETE http://localhost:8000/api/cookies
curl -X POST http://localhost:8000/api/warmup
```

### ❌ Browser tidak mau start
```bash
# Install/reinstall Chromium
playwright install chromium
playwright install-deps chromium  # Linux only
```

### ❌ Import Error saat startup
```bash
# Pastikan virtual env aktif dan semua package terinstall
pip install -r requirements.txt
```

---

## 🐳 Docker (Production)

```yaml
# docker-compose.yml sudah tersedia di root project
docker-compose up --build
```

Untuk production Docker:
- Set `HEADLESS=true` di `.env`
- Warmup dilakukan sekali via API setelah container up
- Cookie tersimpan di volume Docker

---

## 📝 Notes

- **1 Worker only**: Browser adalah singleton — jangan jalankan `--workers > 1`
- **Cookie TTL**: `cf_clearance` biasanya valid 1-7 hari tergantung situs
- **Rate limit**: Backend secara otomatis menambahkan delay 2-5 detik antar request
- **Retry**: Setiap request otomatis retry maksimal 3x dengan exponential backoff

---

*Dibuat untuk keperluan riset hukum dan akses publik putusan pengadilan Indonesia.*
