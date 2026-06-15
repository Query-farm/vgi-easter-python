# Copyright 2026 Query Farm LLC - https://query.farm
#
# Container for the easter VGI worker's HTTP transport (`vgi-easter-http`).
# DuckDB clients ATTACH it over http:// — see README.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md LICENSE easter_worker.py serve.py ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Fly routes external traffic to this internal port (see fly.toml).
EXPOSE 8080
CMD ["vgi-easter-http", "--host", "0.0.0.0", "--port", "8080", "--log-format", "json"]
