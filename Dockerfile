# FundTrail — dev/build image (optional; see docker-compose.yml)
# Slim Python base; installs deps; runs the Flask app.
FROM python:3.11-slim

# System deps some wheels need (lxml/reportlab/pandas build helpers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY main/requirements.txt /app/main/requirements.txt
RUN pip install --no-cache-dir -r /app/main/requirements.txt

# Copy source (data/secrets are excluded via .dockerignore)
COPY . /app

WORKDIR /app/main
EXPOSE 5000

# NOTE: SECRET_KEY must be provided at runtime (env/compose). The app refuses to
# start without it — that is intentional (security finding FT-006).
CMD ["python", "app.py"]
