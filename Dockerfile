# ── Stage 1: Build frontend ──────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ─────────────────────────────────────────
FROM python:3.11-slim
# Install system deps (pg driver build + zizmor)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc curl && \
    # Install zizmor (SAST scanner for GitHub Actions). uname -m returns
    # x86_64 or aarch64 — both match zizmor's release naming directly.
    # Releases are .tar.gz archives containing the binary.
    mkdir -p /tmp/zizmor-extract && \
    curl -fsSL "https://github.com/woodruffw/zizmor/releases/latest/download/zizmor-$(uname -m)-unknown-linux-gnu.tar.gz" \
         -o /tmp/zizmor.tar.gz && \
    tar -xzf /tmp/zizmor.tar.gz -C /tmp/zizmor-extract && \
    BIN_PATH="$(find /tmp/zizmor-extract -name zizmor -type f | head -n 1)" && \
    if [ -z "$BIN_PATH" ]; then echo "zizmor binary not found in archive" >&2 && exit 1; fi && \
    mv "$BIN_PATH" /usr/local/bin/zizmor && \
    chmod +x /usr/local/bin/zizmor && \
    rm -rf /tmp/zizmor.tar.gz /tmp/zizmor-extract && \
    /usr/local/bin/zizmor --version && \
    apt-get purge -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy actionbom core library
COPY actionbom/ ./actionbom/
# Copy top-level requirements (actionbom deps like PyYAML, requests)
COPY requirements.txt ./requirements-core.txt
RUN pip install --no-cache-dir -r requirements-core.txt

# Copy backend
COPY backend/app/ ./app/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./static

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]