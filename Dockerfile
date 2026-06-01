# syntax=docker/dockerfile:1.7

ARG PLAYWRIGHT_VERSION=v1.60.0-noble

# --- Builder stage ------------------------------------------------------------
FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_VERSION} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv (lockfile-aware Python package manager).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency manifests first for layer caching.
COPY mcp-mp/pyproject.toml mcp-mp/uv.lock ./mcp-mp/
COPY scraper/pyproject.toml scraper/uv.lock ./scraper/

# Copy the scraper source so the file:// editable dependency in mcp-mp resolves.
COPY scraper/src/ ./scraper/src/

WORKDIR /build/mcp-mp
RUN uv sync --frozen --extra scraper --no-dev

# Copy the rest of the mcp-mp source after deps are installed (better cache).
COPY mcp-mp/ ./

# --- Runtime stage ------------------------------------------------------------
FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Imports are rooted at /app (which is the mcp-mp package root).
    PYTHONPATH=/app \
    PORT=8080 \
    HOME=/home/mcp \
    MP_LOCAL_ROOT=/var/data/mp-mcp

# Non-root user for defence in depth (Cloud Run runs PID 1 as root by default).
RUN groupadd --system mcp \
    && useradd --system --gid mcp --home-dir /home/mcp --shell /bin/bash mcp \
    && mkdir -p /home/mcp /var/data/mp-mcp \
    && chown -R mcp:mcp /home/mcp /var/data/mp-mcp

WORKDIR /app

# Copy the built virtualenv and the application source.
COPY --from=builder --chown=mcp:mcp /opt/venv /opt/venv
COPY --from=builder --chown=mcp:mcp /build/mcp-mp /app
COPY --from=builder --chown=mcp:mcp /build/scraper /scraper

USER mcp

EXPOSE 8080

# Cloud Run injects $PORT (default 8080); uvicorn binds 0.0.0.0:$PORT.
# --proxy-headers: Cloud Run terminates TLS upstream, so forwarded headers must
# be trusted so that request.url uses https://.
CMD ["sh", "-c", "exec uvicorn interfaces.mcp.server:create_app --factory --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
