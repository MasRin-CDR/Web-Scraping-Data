FROM python:3.11-slim

# Fix paket untuk Debian Trixie (suffix t64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg2 \
    libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0t64 libatk-bridge2.0-0t64 \
    libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2t64 libatspi2.0-0t64 libwayland-client0 \
    fonts-noto-cjk fonts-liberation fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Context = root project, copy requirements dari BACKEND
COPY BACKEND/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (deps sudah di-install manual di atas)
RUN python -m playwright install chromium

# Copy BACKEND ke /app
COPY BACKEND/ .

# Copy FRONTEND ke /app/FRONTEND agar bisa di-serve oleh FastAPI
COPY FRONTEND/ ./FRONTEND/

RUN mkdir -p data/pdfs data/browser_profile logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
