FROM python:3.11-slim

WORKDIR /app

COPY crawler_worker/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 51668

CMD ["uvicorn", "crawler_worker.main:app", "--host", "0.0.0.0", "--port", "51668"]
