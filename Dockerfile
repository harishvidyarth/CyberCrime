# ──────────────────────────────────────────────────────────────────
# FundTrail v2.0 — container image
#   Build:  docker compose build
#   Run:    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") docker compose up -d
# The SQLite database lives on the /data volume and survives rebuilds.
# ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FUNDTRAIL_DATA_DIR=/data \
    HOME=/data \
    PORT=5050

WORKDIR /app

# pycairo (transitive: xhtml2pdf -> svglib -> rlPyCairo) has no Linux wheel and
# compiles against the cairo headers, hence the build packages here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc pkg-config libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first — cached layer, rebuilds only when requirements change.
COPY main/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

# Application code (".dockerignore" keeps .env, DBs, uploads and letters out).
COPY main/ .

# Non-root user; the app writes /data (DB, logs via HOME) and /app
# (uploads/, generated_letters/, ifsc_state_cache.json).
RUN useradd -r fundtrail && mkdir -p /data && chown -R fundtrail /data /app
USER fundtrail
VOLUME /data
EXPOSE 5050

# Uses the app's own /healthz endpoint (no curl needed on slim).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5050/healthz', timeout=4).status==200 else 1)"

# app.py initialises/migrates/seeds the DB at import time. --preload makes the
# MASTER do that exactly once before forking — without it, parallel workers race
# to seed the first users (UNIQUE constraint crash).
CMD ["gunicorn", "--preload", "--workers", "2", "--bind", "0.0.0.0:5050", "--timeout", "120", "app:app"]
