# ─── Stage 1: Build ────────────────────────────────────────────────────────────
# Contains gcc and build headers; discarded after this stage.
FROM python:3.13.12-slim-bookworm AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

# Build-time deps only — not carried into the runtime image
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./

# Install into an isolated venv so the whole directory can be copied cleanly
ENV UV_HTTP_TIMEOUT=120

RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv -r pyproject.toml psycopg2-binary \
        --index-url https://mirrors.aliyun.com/pypi/simple/ \
        --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# ─── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.13.12-slim-bookworm

WORKDIR /app

# Only the runtime library; headers and gcc are not needed here
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv — no compiler required
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user before COPY so --chown avoids a separate chown layer
RUN addgroup --system jarvis \
 && adduser --system --ingroup jarvis --home /home/jarvis jarvis \
 && mkdir -p /home/jarvis

COPY --chown=jarvis:jarvis . .

RUN chmod +x entrypoint.sh

USER jarvis

CMD ["./entrypoint.sh"]
