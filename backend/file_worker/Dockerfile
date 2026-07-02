FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libxcb1 libx11-xcb1 libxrender1 libxext6 \
    libxcomposite1 libxcursor1 libxdamage1 libxi6 libxtst6 \
    libnss3 libcups2 libxss1 libxrandr2 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 libgl1 --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY file_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY file_worker/main.py .

EXPOSE 51667

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "51667"]
