# JARVIS 可观测性与日志系统设计

**日期**：2026-02-26
**分支**：feature/logs
**状态**：已确认

---

## 背景

JARVIS 通过 `docker compose up -d` 启动后，所有容器均无结构化日志、无日志聚合、无轮转配置，不符合生产部署标准。本次设计目标是补全完整可观测性基础设施。

## 现状问题

| 问题 | 风险 |
|------|------|
| Docker 无日志轮转 | 长期运行磁盘爆满 |
| 无日志聚合服务 | 故障时无法集中排查 |
| 后端仅 3 处标准 logging，无结构化输出 | API 问题无法追踪 |
| 前端 catch 块静默，无错误上报 | Bug 无法主动发现 |
| Nginx、Traefik 无访问日志配置 | 入口流量无记录 |

---

## 整体架构

```
各容器 stdout (JSON)
        │
Docker json-file driver (max-size: 10m, max-file: 3)
        │
   Promtail 采集
(挂载 /var/lib/docker/containers)
        │
    Loki 存储
   (保留 7 天)
        │
   Grafana 展示
(日志 + 现有 Prometheus 指标统一入口)
```

**选型**：Loki + Promtail 方案（方案 A）

理由：与现有 Prometheus + Grafana 体系统一，轻量（合计约 200MB RAM），Grafana Labs 官方推荐生产搭配。

---

## 模块设计

### 1. Docker 基础设施层

**所有容器统一添加日志轮转**：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

**新增 Loki 服务**：

```yaml
loki:
  image: grafana/loki:3.4.2
  volumes:
    - ${HOME}/jarvis-data/loki:/loki
  # 7 天保留期
```

**新增 Promtail 服务**：

```yaml
promtail:
  image: grafana/promtail:3.4.2
  volumes:
    - ${HOME}/jarvis-data/promtail:/promtail-data
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
```

**数据目录**（统一存放于 `~/jarvis-data/`）：

```
~/jarvis-data/
├── postgres/     # 已有
├── qdrant/       # 已有
├── redis/        # 已有
├── minio/        # 已有
├── prometheus/   # 已有
├── grafana/      # 已有
├── loki/         # 新增
└── promtail/     # 新增（存储 positions.yaml）
```

### 2. 后端结构化日志层

**日志库**：structlog（支持 asyncio context binding，JSON 输出，高性能）

**每条日志标准字段**：

```json
{
  "timestamp": "2026-02-26T10:00:00.123Z",
  "level": "info",
  "logger": "app.api.chat",
  "trace_id": "a1b2c3d4",
  "user_id": "uuid-xxx",
  "method": "POST",
  "path": "/api/chat/stream",
  "status_code": 200,
  "duration_ms": 342,
  "event": "request completed"
}
```

**新增文件**：

- `backend/app/core/logging.py` — structlog 初始化配置，支持 `LOG_LEVEL` 环境变量
- `backend/app/core/logging_middleware.py` — ASGI 中间件，每请求生成 `trace_id`，记录请求进入/响应完成/异常，响应头返回 `X-Trace-ID`

**全量审计日志覆盖点**：

| 文件 | 记录内容 |
|------|---------|
| `api/auth.py` | 登录成功/失败、注册、token 过期 |
| `api/chat.py` | 消息发送、流式开始/结束、Agent 错误 |
| `api/conversations.py` | 对话创建/删除 |
| `api/documents.py` | 文档上传/删除、RAG 索引完成 |
| `api/settings.py` | 设置修改（不记录 API key 明文） |
| `agent/graph.py` | Agent 执行开始/结束、工具调用名称 |

**新增客户端错误上报接口**：

- `POST /api/logs/client-error` — 接收前端错误上报，用 structlog 记录

**新增依赖**：`structlog`（加入 `backend/pyproject.toml`）

### 3. 监控配置层

**新增文件**：

```
monitoring/
├── loki/
│   └── loki-config.yaml          # Loki 配置，7 天保留期
├── promtail/
│   └── promtail-config.yaml      # 采集所有容器日志，按 container_name 打标签
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── loki.yaml          # Loki 数据源（自动 provision）
        └── dashboards/
            └── logs.json          # 日志仪表板（按服务过滤、错误高亮、trace_id 搜索）
```

### 4. 前端错误处理层

**全局错误捕获**（`frontend/src/main.ts`）：

- `app.config.errorHandler` — Vue 组件错误
- `window.onerror` — 全局 JS 错误
- `window.addEventListener('unhandledrejection', ...)` — 未处理的 Promise rejection

**错误上报**：统一通过 `POST /api/logs/client-error` 发送至后端，自动附带响应头中的 `X-Trace-ID`

**修复静默 catch 块**：`chat.ts` 等 store 中的空 `catch {}` 改为记录错误信息

### 5. 环境变量

**`.env` / `.env.example` 新增**：

```bash
# 日志配置
LOG_LEVEL=INFO    # DEBUG / INFO / WARNING / ERROR
```

---

## 不在范围内

- Sentry 错误追踪（用 Loki 查询替代）
- OpenTelemetry 分布式追踪
- 前端 Web Vitals 上报
- PostgreSQL 慢查询日志

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `docker-compose.yml` | 新增 loki、promtail 服务；所有容器加 logging 轮转 |
| `monitoring/loki/loki-config.yaml` | 新增 |
| `monitoring/promtail/promtail-config.yaml` | 新增 |
| `monitoring/grafana/provisioning/datasources/loki.yaml` | 新增 |
| `monitoring/grafana/provisioning/dashboards/logs.json` | 新增 |
| `backend/pyproject.toml` | 新增 structlog 依赖 |
| `backend/app/core/logging.py` | 新增 |
| `backend/app/core/logging_middleware.py` | 新增 |
| `backend/app/main.py` | 注册 logging 配置和中间件 |
| `backend/app/api/auth.py` | 新增审计日志 |
| `backend/app/api/chat.py` | 新增审计日志 |
| `backend/app/api/conversations.py` | 新增审计日志 |
| `backend/app/api/documents.py` | 新增审计日志 |
| `backend/app/api/settings.py` | 新增审计日志 |
| `backend/app/api/logs.py` | 新增（客户端错误上报接口） |
| `backend/app/agent/graph.py` | 新增 Agent 执行日志 |
| `frontend/src/main.ts` | 新增全局错误捕获 |
| `frontend/src/stores/chat.ts` | 修复静默 catch 块 |
| `.env.example` | 新增 LOG_LEVEL |
