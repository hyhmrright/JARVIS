FROM python:3.13.12-slim-bookworm

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY . .

RUN addgroup --system jarvis \
 && adduser --system --ingroup jarvis --home /home/jarvis jarvis \
 && mkdir -p /home/jarvis \
 && chown -R jarvis:jarvis /app /home/jarvis \
 && chmod +x entrypoint.sh

USER jarvis

CMD ["./entrypoint.sh"]
