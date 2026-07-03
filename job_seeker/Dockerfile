FROM python:3.10-slim

WORKDIR /app

# Install Chromium dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps 2>/dev/null || true

# Copy application code
COPY stealth.py boss_crawler.py crawler_service.py ./

# Create data directory for cookies
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "crawler_service:app", "--host", "0.0.0.0", "--port", "8000"]
