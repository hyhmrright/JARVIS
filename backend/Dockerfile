FROM python:3.13.12-slim-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY . .

# 创建非 root 系统用户，降低容器逃逸风险
RUN addgroup --system jarvis \
 && adduser --system --ingroup jarvis jarvis \
 && chown -R jarvis:jarvis /app

USER jarvis

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
