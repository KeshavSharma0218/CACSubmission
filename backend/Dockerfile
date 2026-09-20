FROM python:3.12-slim

# System deps: libpq for asyncpg build fallback, curl for the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# uv is Anthropic's recommended-in-spec dependency manager: much faster installs than
# pip, and it produces a reproducible lockfile.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first so Docker can cache the install layer and only
# re-run it when dependencies actually change, not on every source-code edit.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
