FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 51669

CMD ["uvicorn", "rag_worker.main:app", "--host", "0.0.0.0", "--port", "51669"]
