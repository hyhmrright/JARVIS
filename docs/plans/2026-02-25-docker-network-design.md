# Docker 部署架构升级设计

**日期**：2026-02-25
**分支**：`docker-compose`
**状态**：已批准，待实现

---

## 目标

将现有 docker-compose 单网络扁平部署升级为生产可用的分层隔离架构，同时引入全栈可观测性（Prometheus + Grafana）。

---

## 背景与现状

当前部署存在以下问题：

- 所有服务共享 Docker 默认网络，frontend 可直接访问 postgres/redis 等基础设施
- postgres(5432)、redis(6379)、qdrant(6333)、minio(9000/9001)、backend(8000) 全部暴露到宿主机
- backend 容器以 root 用户运行
- 无监控、无自动重启策略
- 无 dev/prod 配置分离

---

## 网络拓扑设计

### 四层网络

```
                    ┌─────────────────────────────────────────┐
  LAN               │  Machine A                              │
  :80 ─────────────►│  Traefik                                │
  :3001 ────────────│──► Grafana                              │
  :8080(dev only)───│──► Traefik Dashboard                    │
                    │                                         │
  [web-net]         │  Traefik ──────────► frontend(nginx)   │
  [app-net]         │  frontend(nginx) ──► backend           │
  [infra-net]       │  backend ──────────► postgres          │
                    │                  ├──► redis             │
                    │                  ├──► qdrant            │
                    │                  └──► minio             │
  [monitor-net]     │  prometheus ──────► cadvisor           │
                    │               ├────► postgres_exporter  │
                    │               ├────► redis_exporter     │
                    │               └────► backend(/metrics)  │
                    │  grafana ─────────► prometheus          │
                    └─────────────────────────────────────────┘
```

### 网络职责

| 网络 | 成员 | 职责 |
|------|------|------|
| `web` | traefik, frontend | 边缘路由层，LAN 入口 |
| `app` | frontend, backend | 应用通信层 |
| `infra` | backend, postgres, redis, qdrant, minio, minio-init | 基础设施层 |
| `monitor` | prometheus, grafana, cadvisor, postgres_exporter, redis_exporter, backend | 监控专用层 |

`backend` 跨 `app` + `infra` + `monitor` 三个网络，是架构桥接核心。

---

## 服务配置

### 对外暴露端口

| 端口 | 服务 | 说明 |
|------|------|------|
| `:80` | Traefik | 唯一业务入口，LAN 内通过 `http://<IP>` 访问 |
| `:3001` | Grafana | 监控面板 |
| `:8080` | Traefik Dashboard | 仅 dev override 开放 |

其余端口（5432/6333/6379/9000/8000 等）全部移除宿主机映射。

### 重启策略

所有长期运行服务统一加 `restart: unless-stopped`。
`minio-init` 为一次性初始化任务，保持 `restart: "no"`。

### 新增监控服务

| 服务 | 镜像 | 职责 |
|------|------|------|
| `traefik` | `traefik:v3` | 边缘反向代理，LAN 入口 |
| `cadvisor` | `gcr.io/cadvisor/cadvisor` | 容器资源指标（CPU/内存/网络） |
| `postgres_exporter` | `prometheuscommunity/postgres-exporter` | PostgreSQL 指标 |
| `redis_exporter` | `oliver006/redis_exporter` | Redis 指标 |
| `prometheus` | `prom/prometheus` | 指标抓取与存储 |
| `grafana` | `grafana/grafana` | 可视化面板，预置 Dashboard |

---

## 代码改动

### backend/Dockerfile — 非 root 用户

新增创建系统用户 `jarvis`，以非 root 身份运行容器进程，降低容器逃逸风险。

### backend/pyproject.toml

新增依赖：`prometheus-fastapi-instrumentator >= 7.0`

### backend/app/main.py

在 `FastAPI` 实例创建后挂载 `/metrics` 端点：

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

自动采集所有路由的请求数、延迟、状态码分布。

---

## 监控配置

### Prometheus 抓取配置（`monitoring/prometheus.yml`）

四个抓取目标，均通过 `monitor` 网络内部 DNS 访问：

- `cadvisor:8080` — 容器资源
- `backend:8000/metrics` — FastAPI 应用指标
- `postgres_exporter:9187` — PostgreSQL
- `redis_exporter:9121` — Redis

抓取间隔：15s

### Grafana 自动预配置

Grafana 启动时自动加载数据源和 Dashboard，无需手动配置：

```
monitoring/grafana/provisioning/
  datasources/prometheus.yml   # 自动添加 Prometheus 数据源
  dashboards/provider.yml      # Dashboard 加载路径配置
```

预置四个 Dashboard：

| Dashboard | Grafana ID | 内容 |
|-----------|-----------|------|
| Docker 容器总览 | 193 | 所有容器 CPU/内存/网络 |
| FastAPI 监控 | 自定义 | 请求数、延迟 P99、错误率 |
| PostgreSQL | 9628 | 连接数、查询、锁 |
| Redis | 763 | 命令数、内存、命中率 |

访问：`http://<IP>:3001`，默认账号 `admin/admin`，首次登录后修改密码。

---

## 配置文件结构

### dev/prod 分离

```bash
# 开发（自动合并 override，开放调试端口）
docker compose up -d

# 生产（只用主文件，最小端口暴露）
docker compose -f docker-compose.yml up -d
```

### 新增文件

```
docker-compose.override.yml       # 开发用：暴露调试端口 + hot-reload
monitoring/
  prometheus.yml                  # Prometheus scrape 配置
  grafana/
    provisioning/
      datasources/prometheus.yml  # 自动配置数据源
      dashboards/provider.yml     # Dashboard 加载配置
      dashboards/jarvis.json      # 预置面板
```

---

## 文档更新范围

| 文件 | 更新内容 |
|------|---------|
| `README.md`（英文主） | 端口变更（3000→80）、新增技术栈（Traefik/Prometheus/Grafana）、新增项目结构（monitoring/）、快速开始命令更新 |
| `docs/i18n/zh/README.md` | 同上，中文版 |
| `docs/i18n/ja/README.md`、`ko`、`fr`、`de` | 同上，各自语言版 |
| `CLAUDE.md`（根目录双语文件，无 i18n 版本） | 常用命令更新（端口、监控访问方式）、项目结构更新 |

---

## 请求路径说明

用户浏览器（Machine B）访问全过程：

```
http://192.168.1.100/
  → Traefik:80 → frontend nginx:80 → Vue SPA

http://192.168.1.100/api/chat/stream
  → Traefik:80 → frontend nginx:80
  → nginx proxy_pass http://backend:8000 (Docker DNS)
  → FastAPI SSE 响应
```

前端 Vue 使用相对路径 `baseURL: "/api"`，无需配置后端 IP，部署机 IP 变更无需修改任何代码。
