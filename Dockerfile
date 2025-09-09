# syntax=docker/dockerfile:1
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source
COPY . /app

# Default env (can be overridden by docker run / compose)
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    DB_HOST=localhost \
    DB_PORT=3306 \
    DB_USER=nl2sql \
    DB_PASSWORD=password \
    DB_NAME=test_db \
    VECTOR_DB_PATH=/app/chroma_db

EXPOSE 8000

CMD ["python", "main.py"]
