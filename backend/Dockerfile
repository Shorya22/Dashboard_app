# Backend image: FastAPI app served via uvicorn.
# Data Excel files under backend/data/ and the SQLite DB directory are
# copied in / mounted so the container has everything it needs at runtime.

FROM python:3.11-slim

WORKDIR /app

# System deps for pandas/openpyxl wheels build cleanly on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# app/data holds the SQLite DB (mounted as a volume in compose so it
# persists across restarts) — make sure the directory exists in the image
# too, for a first run with no volume yet.
RUN mkdir -p /app/app/data

EXPOSE 8000

# Bind 0.0.0.0 inside the container regardless of the .env HOST value —
# HOST there is for local (non-docker) dev where 127.0.0.1 is common.
ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
