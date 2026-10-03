# ── Stage 1: Build C++ engine ─────────────────────────────────────────────────
FROM ubuntu:22.04 AS cpp-builder

RUN apt-get update && apt-get install -y \
    cmake build-essential g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/core
COPY core/ .
RUN mkdir -p build && cd build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release \
    && cmake --build . --config Release

# ── Stage 2: Python API ────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System deps for OSMnx / geopandas
RUN apt-get update && apt-get install -y \
    libgdal-dev libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy C++ binary from builder
COPY --from=cpp-builder /src/core/build/smartroute_engine ./api/smartroute_engine

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY api/   ./api/
COPY ml/    ./ml/
COPY data/  ./data/
COPY models/ ./models/
COPY frontend/ ./frontend/

# Expose API port
EXPOSE 8000

# Run FastAPI
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
