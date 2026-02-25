FROM python:3.13.12-slim-bookworm

WORKDIR /app

RUN pip install uv

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
