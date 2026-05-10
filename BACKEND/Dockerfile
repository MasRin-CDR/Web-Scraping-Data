# ============================================================
# Dockerfile — Mahkamah Agung Scraper
# Multi-stage build with Playwright Chromium
# ============================================================

FROM python:3.11-slim AS base

# System dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg2 \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libwayland-client0 \
    fonts-noto-cjk fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN python -m playwright install chromium && \
    python -m playwright install-deps chromium

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/pdfs data/browser_profile logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
