# Mahkamah Agung Direktori Scraper — Fullstack

Production-grade fullstack web scraper for [putusan3.mahkamahagung.go.id](https://putusan3.mahkamahagung.go.id/direktori.html).

## Architecture

```
mahkamah_scraper/
├── BACKEND/
│   ├── app/
│   │   ├── api/routes.py          # FastAPI endpoints
│   │   ├── scraper/
│   │   │   ├── browser.py         # Stealth Chromium manager
│   │   │   ├── engine.py          # Scraping orchestration
│   │   │   └── parser.py          # BeautifulSoup HTML parser
│   │   ├── services/
│   │   │   └── search_service.py  # Business logic layer
│   │   ├── models/
│   │   │   ├── schemas.py         # Pydantic request/response
│   │   │   └── database.py        # SQLite async layer
│   │   ├── utils/
│   │   │   ├── logger.py          # Loguru logging
│   │   │   └── helpers.py         # Date, URL, text utils
│   │   ├── config.py              # Centralized settings
│   │   └── main.py                # FastAPI app entry
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── FRONTEND/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── docker-compose.yml
```

## Features

| Feature | Details |
|---|---|
| **Frontend** | Modern legal-tech dashboard, dark mode, search filters, pagination, modal detail, CSV export |
| **API** | FastAPI with `/search`, `/detail`, `/download-pdf` endpoints |
| **Scraping** | Playwright Chromium + BeautifulSoup, 3 parsing strategies |
| **Anti-Detection** | Stealth JS, random user-agent, canvas noise, human simulation |
| **Database** | SQLite (async), result caching with TTL, search logging |
| **Retry** | Tenacity exponential backoff on failures |
| **Deployment** | Docker, docker-compose ready |

## Quick Start

### 1. Install Dependencies

```bash
cd BACKEND
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
copy .env.example .env
# Edit .env as needed
```

### 3. Run

```bash
# From BACKEND directory
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Open http://localhost:8000 in your browser
```

### 4. Docker

```bash
# From project root
docker-compose up --build
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/search` | Search putusan (keyword, lokasi, jenis) |
| POST | `/api/detail` | Get full putusan detail |
| GET | `/api/download-pdf?url=` | Proxy PDF download |
| GET | `/api/lokasi` | Court location list |
| GET | `/api/health` | Health check |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Server port |
| `HEADLESS` | `false` | Browser headless mode |
| `MAX_PAGES_PER_SEARCH` | `5` | Max pages to scrape |
| `MAX_RETRIES` | `3` | Retry attempts |
| `CACHE_TTL_SECONDS` | `3600` | Cache duration (1h) |
| `MIN_DELAY` / `MAX_DELAY` | `2.0` / `5.0` | Inter-request delay |

## Legal Notice

Use responsibly. Mahkamah Agung putusan data is public record, but respect rate limits and Terms of Service.
