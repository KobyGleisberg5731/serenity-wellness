FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY app/ .

ENV DATA_DIR=/app/data
ENV PORT=18871
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/data/uploads

EXPOSE 18871

CMD ["gunicorn", "--bind", "0.0.0.0:18871", "--workers", "2", "--timeout", "120", "backend.app:app"]
