# Docker 部署架构升级实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 JARVIS 的 docker-compose 部署从单一扁平网络升级为四层隔离网络 + Traefik 边缘路由 + Prometheus/Grafana 全栈监控，并同步更新所有文档。

**Architecture:** Traefik 作为唯一 LAN 入口监听 `:80`，通过 `web` 网络路由到 frontend nginx；frontend nginx 经 `app` 网络代理 `/api` 到 backend；backend 经 `infra` 网络访问 postgres/redis/qdrant/minio；monitoring 服务走独立的 `monitor` 网络抓取各层指标。

**Tech Stack:** Docker Compose · Traefik v3 · Prometheus · Grafana · prometheus-fastapi-instrumentator · cAdvisor · postgres_exporter · redis_exporter

---

## Task 1: Backend Dockerfile — 非 root 用户

**Files:**
- Modify: `backend/Dockerfile`

**Step 1: 修改 Dockerfile，新增 non-root 用户**

将 `backend/Dockerfile` 完整替换为：

```dockerfile
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
```

**Step 2: 验证 Dockerfile 语法**

```bash
docker build -t jarvis-backend-test ./backend
```

预期：构建成功，无报错。

**Step 3: 验证容器运行用户**

```bash
docker run --rm --entrypoint whoami jarvis-backend-test
```

预期：输出 `jarvis`（非 `root`）。

**Step 4: 清理测试镜像**

```bash
docker rmi jarvis-backend-test
```

**Step 5: Commit**

```bash
git add backend/Dockerfile
git commit -m "feat(docker): run backend as non-root user jarvis"
```

---

## Task 2: 添加 Prometheus 指标端点

**Files:**
- Modify: `backend/pyproject.toml`（`"httpx>=0.28.0",` 之后添加）
- Modify: `backend/app/main.py`（第 38-39 行之后）

**Step 1: 在 pyproject.toml 的 dependencies 列表中，`"httpx>=0.28.0",` 之后添加**

```toml
    "prometheus-fastapi-instrumentator>=7.0",
```

**Step 2: 安装依赖**

```bash
cd backend && uv sync
```

**Step 3: 在 main.py 中，import 区域末尾添加**

```python
from prometheus_fastapi_instrumentator import Instrumentator
```

在 `app.state.limiter = limiter` 之后添加：

```python
Instrumentator().instrument(app).expose(app)
```

**Step 4: 验证语法**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

预期：输出 `OK`。

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/main.py
git commit -m "feat(backend): expose /metrics endpoint for Prometheus scraping"
```

---

## Task 3: 重写 docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: 完整替换 docker-compose.yml**

```yaml
networks:
  web:
    driver: bridge
  app:
    driver: bridge
  infra:
    driver: bridge
  monitor:
    driver: bridge

services:
  postgres:
    image: postgres:18.2-bookworm
    networks: [infra]
    restart: unless-stopped
    environment:
      POSTGRES_DB: jarvis
      POSTGRES_USER: jarvis
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATA: /var/lib/postgresql/18/docker
    volumes:
      - ${HOME}/jarvis-data/postgres:/var/lib/postgresql/18/docker
      - ./database/postgres:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jarvis"]
      interval: 5s
      timeout: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.17.0
    networks: [infra]
    restart: unless-stopped
    volumes:
      - ${HOME}/jarvis-data/qdrant:/qdrant/storage
    healthcheck:
      test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/localhost/6333 && printf 'GET /readyz HTTP/1.0\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && timeout 2 cat <&3 | grep -q '200 OK'"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:8.6.0-alpine3.23
    networks: [infra]
    restart: unless-stopped
    command: redis-server /usr/local/etc/redis/redis.conf --requirepass ${REDIS_PASSWORD}
    volumes:
      - ${HOME}/jarvis-data/redis:/data
      - ./database/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a ${REDIS_PASSWORD} ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:RELEASE.2025-09-07T16-13-09Z
    networks: [infra]
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ${HOME}/jarvis-data/minio:/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9000/minio/health/live || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio-init:
    image: quay.io/minio/mc:latest
    networks: [infra]
    depends_on:
      minio:
        condition: service_healthy
    restart: "no"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    entrypoint: >
      /bin/sh -c "
      mc alias set jarvis http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD;
      mc mb --ignore-existing jarvis/jarvis-documents;
      exit 0;
      "

  backend:
    build: ./backend
    networks: [app, infra, monitor]
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://jarvis:${POSTGRES_PASSWORD}@postgres:5432/jarvis
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379
      QDRANT_URL: http://qdrant:6333
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      JWT_SECRET: ${JWT_SECRET}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\""]
      interval: 5s
      timeout: 5s
      retries: 5

  frontend:
    build: ./frontend
    networks: [web, app]
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=PathPrefix(`/`)"
      - "traefik.http.routers.frontend.entrypoints=web"
      - "traefik.http.services.frontend.loadbalancer.server.port=80"
      - "traefik.docker.network=web"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:80/ > /dev/null || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  traefik:
    image: traefik:v3.3
    networks: [web]
    restart: unless-stopped
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--api.dashboard=true"
      - "--api.insecure=true"
    ports:
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    networks: [monitor]
    restart: unless-stopped
    privileged: true
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:latest
    networks: [infra, monitor]
    restart: unless-stopped
    environment:
      DATA_SOURCE_NAME: postgresql://jarvis:${POSTGRES_PASSWORD}@postgres:5432/jarvis?sslmode=disable
    depends_on:
      postgres:
        condition: service_healthy

  redis_exporter:
    image: oliver006/redis_exporter:latest
    networks: [infra, monitor]
    restart: unless-stopped
    environment:
      REDIS_ADDR: redis://redis:6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
    depends_on:
      redis:
        condition: service_healthy

  prometheus:
    image: prom/prometheus:latest
    networks: [monitor]
    restart: unless-stopped
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ${HOME}/jarvis-data/prometheus:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=30d"

  grafana:
    image: grafana/grafana:latest
    networks: [monitor]
    restart: unless-stopped
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
    volumes:
      - ${HOME}/jarvis-data/grafana:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
```

**Step 2: 验证 YAML 语法**

```bash
docker compose config --quiet
```

预期：无报错输出。

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker): add 4-network isolation + Traefik + monitoring services"
```

---

## Task 4: 创建 docker-compose.override.yml（开发用）

**Files:**
- Create: `docker-compose.override.yml`

**Step 1: 创建文件**

```yaml
# docker-compose.override.yml
# 本地开发自动合并此文件，生产部署用:
#   docker compose -f docker-compose.yml up -d
services:
  backend:
    environment:
      UVICORN_RELOAD: "1"
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"

  traefik:
    ports:
      - "8080:8080"

  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  qdrant:
    ports:
      - "6333:6333"

  minio:
    ports:
      - "9000:9000"
      - "9001:9001"
```

**Step 2: 验证合并结果**

```bash
docker compose config --quiet
```

预期：无报错，backend 服务含 `UVICORN_RELOAD` 环境变量。

**Step 3: Commit**

```bash
git add docker-compose.override.yml
git commit -m "feat(docker): add dev override with debug ports and hot-reload"
```

---

## Task 5: 更新 init-env.sh，添加 GRAFANA_PASSWORD

**Files:**
- Modify: `scripts/init-env.sh`

**Step 1: 在 `ENCRYPTION_KEY=$(gen_fernet_key)` 之后添加**

```bash
GRAFANA_PASSWORD=$(rand_password)
```

**Step 2: 在 heredoc 的 `# LLM` 注释之前添加**

```bash
# Monitoring
GRAFANA_PASSWORD=${GRAFANA_PASSWORD}

```

**Step 3: 验证**

```bash
bash scripts/init-env.sh /tmp/test-env.env && grep GRAFANA /tmp/test-env.env && rm /tmp/test-env.env
```

预期：输出 `GRAFANA_PASSWORD=<随机密码>`。

**Step 4: Commit**

```bash
git add scripts/init-env.sh
git commit -m "feat(scripts): add GRAFANA_PASSWORD to init-env.sh"
```

---

## Task 6: 创建 monitoring/prometheus.yml

**Files:**
- Create: `monitoring/prometheus.yml`

**Step 1: 创建目录并写入配置**

```bash
mkdir -p monitoring
```

创建 `monitoring/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: cadvisor
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: backend
    static_configs:
      - targets: ['backend:8000']
    metrics_path: /metrics

  - job_name: postgres
    static_configs:
      - targets: ['postgres_exporter:9187']

  - job_name: redis
    static_configs:
      - targets: ['redis_exporter:9121']
```

**Step 2: Commit**

```bash
git add monitoring/prometheus.yml
git commit -m "feat(monitoring): add Prometheus scrape config"
```

---

## Task 7: 创建 Grafana provisioning 配置

**Files:**
- Create: `monitoring/grafana/provisioning/datasources/prometheus.yml`
- Create: `monitoring/grafana/provisioning/dashboards/provider.yml`

**Step 1: 创建目录**

```bash
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
```

**Step 2: 创建数据源配置 `monitoring/grafana/provisioning/datasources/prometheus.yml`**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

**Step 3: 创建 Dashboard provider 配置 `monitoring/grafana/provisioning/dashboards/provider.yml`**

```yaml
apiVersion: 1

providers:
  - name: jarvis
    folder: JARVIS
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Step 4: Commit**

```bash
git add monitoring/
git commit -m "feat(monitoring): add Grafana provisioning for Prometheus datasource"
```

---

## Task 8: 全栈验证

**Step 1: 构建并启动所有服务**

```bash
docker compose up -d --build
```

**Step 2: 等待所有服务健康**

```bash
docker compose ps
```

预期：所有服务状态为 `healthy` 或 `running`（minio-init 为 `Exited (0)`）。

**Step 3: 验证前端可访问**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/
```

预期：`200`

**Step 4: 验证 API 路由**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health
```

预期：`200`

**Step 5: 验证 Grafana 可访问**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001
```

预期：`200`

**Step 6: 验证网络隔离（frontend 不能直接访问 postgres）**

```bash
docker compose exec frontend sh -c "nc -zv postgres 5432" 2>&1
```

预期：DNS 解析失败（frontend 不在 infra 网络）。

**Step 7: 验证 backend 以非 root 运行**

```bash
docker compose exec backend whoami
```

预期：`jarvis`

**Step 8: 停止服务**

```bash
docker compose down
```

---

## Task 9: 更新 README.md（英文主版本）和 docs/i18n/zh/README.md（中文版）

**Files:**
- Modify: `README.md`（英文主，根目录）
- Modify: `docs/i18n/zh/README.md`（中文 i18n）

**变更点：**

1. 特性列表中 `Full-Stack Docker` 条目改为：
```markdown
- **Full-Stack Docker** — One-command `docker compose up -d`; 4-layer network isolation for security
- **Observability** — Traefik edge routing · Prometheus metrics · Grafana visualization dashboards
```

2. 技术栈表格新增行：
```markdown
| Deployment | Traefik · Prometheus · Grafana · Docker Networks |
```

3. 项目结构在 `docker-compose.yml` 行后添加：
```
├── docker-compose.override.yml  # Dev override (debug ports + hot-reload)
├── monitoring/                  # Prometheus & Grafana config
│   ├── prometheus.yml
│   └── grafana/provisioning/
```

4. 快速开始服务地址改为：
```
- App: http://localhost (via Traefik)
- Monitoring: http://localhost:3001 (Grafana)
- Traefik Dashboard: http://localhost:8080 (dev only)
```

5. 新增 Production deploy 小节：
```markdown
### Production Deploy (no debug ports)
docker compose -f docker-compose.yml up -d
```

**Step 1: 更新 README.md（英文主版本）**

**Step 2: 更新 docs/i18n/zh/README.md（中文，对应翻译上述变更）**

**Step 3: Commit**

```bash
git add README.md docs/i18n/zh/README.md
git commit -m "docs: update README (en/zh) for new Docker network architecture"
```

---

## Task 10: 更新多语言 README（ja/ko/fr/de）

**Files:**
- Modify: `docs/i18n/ja/README.md`
- Modify: `docs/i18n/ko/README.md`
- Modify: `docs/i18n/fr/README.md`
- Modify: `docs/i18n/de/README.md`

对每个文件应用与 Task 9 相同的变更，翻译为对应语言。

**Step 1: 依次更新 4 个文件**

**Step 2: Commit**

```bash
git add docs/i18n/ja/ docs/i18n/ko/ docs/i18n/fr/ docs/i18n/de/
git commit -m "docs: update i18n READMEs (ja/ko/fr/de) for new Docker architecture"
```

---

## Task 11: 更新 CLAUDE.md（根目录双语文件，无 i18n 版本）

**Files:**
- Modify: `CLAUDE.md`

**变更点：**

1. 核心架构项目结构中，`docker-compose.yml` 行后添加：
```
├── docker-compose.override.yml  # Dev override (debug ports + hot-reload) / 开发用 override
├── monitoring/                  # Monitoring config / 监控配置
│   ├── prometheus.yml
│   └── grafana/provisioning/
```

2. 常用命令 — 全栈 Docker 部分改为：
```bash
# Full-stack Docker (dev, auto-merges override) / 全栈 Docker（开发，自动合并 override）
docker compose up -d                  # App :80 · Grafana :3001 · Traefik Dashboard :8080

# Full-stack Docker (production, minimal ports) / 全栈 Docker（生产，无调试端口）
docker compose -f docker-compose.yml up -d
```

**Step 1: 更新 CLAUDE.md**

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new Docker architecture"
```

---

## 最终验证清单

- [ ] `docker compose config --quiet` 无报错
- [ ] `curl http://localhost/` 返回 200
- [ ] `curl http://localhost/api/health` 返回 200
- [ ] `curl http://localhost:3001` 返回 200（Grafana）
- [ ] `docker compose exec frontend sh -c "nc -zv postgres 5432"` 返回 DNS 解析失败（网络隔离验证）
- [ ] `docker compose exec backend whoami` 返回 `jarvis`（非 root）
- [ ] Grafana 数据源 Prometheus 状态为 OK
- [ ] minio-init 状态为 `Exited (0)`，未反复重启
