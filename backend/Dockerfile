FROM python:3.13.12-slim-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY . .

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
