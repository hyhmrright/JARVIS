FROM python:3.13.12-slim-bookworm

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install dependencies into the system environment to avoid .venv conflicts in Docker
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml psycopg2-binary

COPY . .

RUN addgroup --system jarvis \
 && adduser --system --ingroup jarvis --home /home/jarvis jarvis \
 && mkdir -p /home/jarvis \
 && chown -R jarvis:jarvis /app /home/jarvis \
 && chmod +x entrypoint.sh

USER jarvis

CMD ["./entrypoint.sh"]
