FROM python:3.12-slim

WORKDIR /app

# System deps for Playwright + lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    wget \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser (Chromium only — smallest)
RUN playwright install chromium --with-deps

# Copy scraper code
COPY . /app/scrapers

# API models are available via PYTHONPATH
ENV PYTHONPATH=/app:/app/api

WORKDIR /app

CMD ["python", "-m", "scrapers.cli", "run", "--source", "all"]
