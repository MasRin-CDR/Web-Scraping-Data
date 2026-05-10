<div align="center">

# ⚖️ Web Scraping Data — Direktori Putusan Mahkamah Agung RI

**Production-grade fullstack web scraper untuk Direktori Putusan Pengadilan Indonesia**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-1.44-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Features](#-features) · [Quick Start](#-quick-start) · [API Docs](#-api-endpoints) · [Deploy](#-deployment) · [Contributing](#-contributing)

</div>

---

## 📋 Overview

Aplikasi fullstack untuk melakukan **web scraping data putusan pengadilan** dari situs resmi [Mahkamah Agung RI](https://putusan3.mahkamahagung.go.id/direktori.html). Dibangun dengan arsitektur modern, scraper ini mampu menghadapi proteksi **Cloudflare Turnstile**, menyimpan data ke database lokal, dan menampilkan hasil melalui dashboard interaktif.

### 🎯 Target Website
```
https://putusan3.mahkamahagung.go.id/direktori.html
```

---

## ✨ Features

### Backend
| Feature | Description |
|---|---|
| 🕷️ **Stealth Scraping** | Playwright Chromium dengan anti-detection JS injection |
| 🛡️ **Cloudflare Bypass** | Interactive warm-up flow untuk Turnstile challenge |
| 🍪 **Persistent Cookies** | Browser profile disimpan untuk reuse sesi |
| 🔄 **Auto-Retry** | Tenacity exponential backoff pada error |
| 💾 **SQLite Cache** | Search results di-cache dengan TTL |
| 📄 **PDF Download** | Proxy download putusan PDF |
| 📊 **3 Parsing Strategies** | Table → Card → Anchor (auto fallback) |
| 📝 **Structured Logging** | Loguru console + rotating file |

### Frontend
| Feature | Description |
|---|---|
| 🎨 **Modern Dashboard** | Legal-tech design dengan glassmorphism |
| 🌙 **Dark Mode** | Full light/dark theme support |
| 🔍 **Smart Search** | Searchable dropdowns + real-time filter |
| 📋 **Sortable Table** | Click-to-sort pada semua kolom |
| 📥 **CSV Export** | One-click data export |
| 📱 **Responsive** | Mobile-first design |
| ⏳ **Skeleton Loading** | Animated loading state |
| 🔔 **Toast Notifications** | Real-time status feedback |

---

## 📸 Screenshots

<div align="center">

| Light Mode | Dark Mode |
|---|---|
| ![Light Mode](docs/screenshot-light.png) | ![Dark Mode](docs/screenshot-dark.png) |

| Warmup Flow | Search Results |
|---|---|
| ![Warmup](docs/screenshot-warmup.png) | ![Results](docs/screenshot-results.png) |

</div>

> 📌 *Screenshots akan ditambahkan setelah deployment*

---

## 📁 Project Structure

```
Web-Scraping-Data/
├── BACKEND/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py              # FastAPI route definitions
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py            # Async SQLite layer (aiosqlite)
│   │   │   └── schemas.py             # Pydantic request/response models
│   │   ├── scraper/
│   │   │   ├── __init__.py
│   │   │   ├── browser.py             # Stealth Chromium browser manager
│   │   │   ├── engine.py              # Scraping orchestrator + retry
│   │   │   └── parser.py              # BeautifulSoup HTML parser
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── search_service.py      # Business logic layer
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── helpers.py             # Date parsing, URL builders
│   │   │   └── logger.py              # Loguru structured logging
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic-settings configuration
│   │   └── main.py                    # FastAPI app entry point
│   ├── data/                          # Runtime data (gitignored)
│   ├── logs/                          # Log files (gitignored)
│   ├── Dockerfile
│   └── requirements.txt
│
├── FRONTEND/
│   ├── index.html                     # Dashboard UI
│   ├── style.css                      # Premium CSS + dark mode
│   └── app.js                         # Vanilla JS — API integration
│
├── docs/                              # Documentation & screenshots
├── .env.example                       # Environment template (safe)
├── .env.local                         # Local env config (keys only)
├── .env.staging                       # Staging env config (keys only)
├── .env.production                    # Production env config (keys only)
├── .gitignore
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- **Python** 3.11+
- **pip** or **uv** package manager
- **Git**

### 1. Clone Repository

```bash
git clone https://github.com/MasRin-CDR/Web-Scaping-Data.git
cd Web-Scaping-Data
```

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Or use specific environment
cp .env.local .env        # Development
cp .env.staging .env      # Staging
cp .env.production .env   # Production
```

> ⚠️ **PENTING**: Isi value pada file `.env` sesuai kebutuhan. File `.env` tidak akan ter-commit ke repository.

### 3. Install Dependencies

```bash
cd BACKEND

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install packages
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium
```

### 4. Run Application

```bash
# From BACKEND directory
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 5. Open Dashboard

```
http://127.0.0.1:8000
```

### 6. Cloudflare Verification

1. Klik tombol **"Mulai Verifikasi"** pada banner orange
2. Selesaikan Cloudflare Turnstile di jendela Chromium
3. Banner berubah hijau ✅ → siap untuk pencarian

---

## 🐳 Deployment

### Docker

```bash
# Build & run
docker-compose up --build -d

# View logs
docker-compose logs -f scraper-api

# Stop
docker-compose down
```

### Manual Deployment

```bash
# Production mode
APP_ENV=production python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
```

> ⚠️ **Note**: Hanya gunakan 1 worker karena Playwright browser instance bersifat shared/singleton.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check + status cf_clearance |
| `POST` | `/api/warmup` | Mulai proses verifikasi Cloudflare |
| `GET` | `/api/warmup-status` | Cek status verifikasi (polling) |
| `POST` | `/api/search` | Cari putusan (cache → scrape → DB) |
| `POST` | `/api/detail` | Ambil detail putusan |
| `GET` | `/api/download-pdf` | Download PDF putusan |
| `GET` | `/api/lokasi` | Daftar lokasi pengadilan |

### Example: Search

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "korupsi", "page": 1, "per_page": 20}'
```

### Example: Detail

```bash
curl -X POST http://localhost:8000/api/detail \
  -H "Content-Type: application/json" \
  -d '{"url": "https://putusan3.mahkamahagung.go.id/direktori/putusan/..."}'
```

---

## ⚙️ Environment Variables

| Variable | Description | Example |
|---|---|---|
| `APP_NAME` | Application name | `Mahkamah Scraper` |
| `APP_ENV` | Environment | `local` / `staging` / `production` |
| `APP_DEBUG` | Debug mode | `true` / `false` |
| `APP_PORT` | Server port | `8000` |
| `PLAYWRIGHT_HEADLESS` | Headless browser | `true` / `false` |
| `SCRAPER_TIMEOUT` | Request timeout (sec) | `60` |
| `SCRAPER_RETRY` | Max retry count | `3` |
| `LOG_LEVEL` | Logging level | `INFO` / `DEBUG` |
| `CACHE_TTL_SECONDS` | Cache expiry (sec) | `3600` |

> 📄 Lihat [.env.example](.env.example) untuk daftar lengkap

---

## 🔧 Troubleshooting

### Cloudflare 403 Forbidden
```
Solusi: Klik "Mulai Verifikasi" di dashboard dan selesaikan
        Turnstile challenge di jendela Chromium.
```

### Browser Not Starting
```bash
# Re-install Playwright browser
python -m playwright install chromium

# Install system dependencies (Linux)
python -m playwright install-deps
```

### Port Already In Use
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>
```

### Database Locked
```
Solusi: Pastikan hanya satu instance server berjalan.
        Delete file data/mahkamah.db untuk reset database.
```

### Module Not Found
```bash
# Pastikan virtual environment aktif
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac

# Re-install dependencies
pip install -r requirements.txt
```

---

## 🛡️ Security

- ✅ Credentials **TIDAK** di-commit ke repository
- ✅ File `.env` ada di `.gitignore`
- ✅ Hanya key templates yang di-upload (`.env.example`, `.env.local`, etc.)
- ✅ Browser profile dan cookies di-gitignore
- ✅ Database files di-gitignore

---

## 📄 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Scraping** | Playwright, BeautifulSoup4, lxml |
| **Database** | SQLite (aiosqlite) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Logging** | Loguru |
| **Config** | pydantic-settings |
| **Retry** | Tenacity |
| **Deploy** | Docker, Docker Compose |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

<div align="center">

**Made with ❤️ by [MasRin-CDR](https://github.com/MasRin-CDR)**

⭐ Star this repo if you find it useful!

</div>
