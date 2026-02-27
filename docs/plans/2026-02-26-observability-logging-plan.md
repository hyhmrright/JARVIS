# Observability & Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add production-grade observability to JARVIS: Docker log rotation, Loki+Promtail log aggregation, structlog structured logging on the backend, full audit logs, and frontend error reporting.

**Architecture:** All containers emit JSON to stdout → Docker json-file driver (with rotation) → Promtail collects → Loki stores (7-day retention) → Grafana displays alongside existing Prometheus metrics. Backend uses structlog with a trace ID middleware; frontend reports errors to a new `/api/logs/client-error` endpoint.

**Tech Stack:** structlog, Loki 3.4.2, Promtail 3.4.2, Grafana (existing), Docker json-file logging driver

---

## Task 1: Add structlog dependency

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add structlog to dependencies**

In `backend/pyproject.toml`, add `"structlog>=25.0.0"` to the `dependencies` list after the `prometheus-fastapi-instrumentator` line.

**Step 2: Install the dependency**

```bash
cd backend && uv add structlog
```

Expected: `uv.lock` updated, `structlog` appears in `uv pip list`.

**Step 3: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add structlog dependency"
```

---

## Task 2: Create structlog configuration module

**Files:**
- Create: `backend/app/core/logging.py`

**Step 1: Create the file**

```python
"""Structlog configuration for JSON-formatted structured logging."""

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON output and standard library integration."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
```

**Step 2: Add `log_level` to config**

In `backend/app/core/config.py`, add to the `Settings` class (after `cors_origins`):

```python
log_level: str = "INFO"
```

**Step 3: Verify import works**

```bash
cd backend && uv run python -c "from app.core.logging import configure_logging; print('ok')"
```

Expected: prints `ok`.

**Step 4: Commit**

```bash
git add backend/app/core/logging.py backend/app/core/config.py
git commit -m "feat: add structlog configuration module"
```

---

## Task 3: Create trace ID middleware

**Files:**
- Create: `backend/app/core/logging_middleware.py`

**Step 1: Create the middleware**

```python
"""ASGI middleware: generates trace_id per request and logs request/response."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        trace_id = str(uuid.uuid4())[:8]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)  # type: ignore[operator]
        except Exception:
            logger.exception("unhandled_exception")
            raise

        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Trace-ID"] = trace_id
        return response
```

**Step 2: Register in main.py**

In `backend/app/main.py`:

1. Replace `import logging` block at top with:
```python
import asyncio

import structlog

from app.core.logging import configure_logging
from app.core.logging_middleware import LoggingMiddleware
```

2. Remove the old `logger = logging.getLogger(__name__)` line.

3. Add `logger = structlog.get_logger(__name__)` after the imports.

4. Before the `app = FastAPI(...)` line, add:
```python
configure_logging()
```

5. After the `app.add_middleware(CORSMiddleware, ...)` block, add:
```python
app.add_middleware(LoggingMiddleware)
```

**Step 3: Verify server starts cleanly**

```bash
cd backend && uv run python -c "from app.main import app; print('ok')"
```

Expected: prints `ok` (no import errors).

**Step 4: Commit**

```bash
git add backend/app/core/logging_middleware.py backend/app/main.py
git commit -m "feat: add trace ID middleware and wire structlog into FastAPI"
```

---

## Task 4: Add audit logs to auth API

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: Add structlog import**

At the top of `backend/app/api/auth.py`, add:
```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add audit log to register endpoint**

In the `register` function, after `await db.commit()`, add:
```python
logger.info("user_registered", user_id=str(user.id), email=body.email)
```

**Step 3: Add audit logs to login endpoint**

In the `login` function:

After the `if not user or not verify_password(...)` check (inside the branch), add:
```python
logger.warning("login_failed", email=body.email)
```

After `return TokenResponse(...)`, add before the return:
```python
logger.info("login_success", user_id=str(user.id), email=user.email)
```

Full updated login function ending:
```python
    if not user or not verify_password(body.password, user.password_hash):
        logger.warning("login_failed", email=body.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    logger.info("login_success", user_id=str(user.id), email=user.email)
    return TokenResponse(access_token=create_access_token(str(user.id)))
```

**Step 4: Commit**

```bash
git add backend/app/api/auth.py
git commit -m "feat: add audit logs to auth endpoints"
```

---

## Task 5: Add audit logs to conversations API

**Files:**
- Modify: `backend/app/api/conversations.py`

**Step 1: Add structlog import**

```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add logs to create_conversation**

After `await db.commit()`:
```python
logger.info("conversation_created", user_id=str(user.id), conv_id=str(conv.id), title=conv.title)
```

**Step 3: Add logs to delete_conversation**

After `await db.commit()`:
```python
logger.info("conversation_deleted", user_id=str(user.id), conv_id=str(conv_id))
```

**Step 4: Commit**

```bash
git add backend/app/api/conversations.py
git commit -m "feat: add audit logs to conversations endpoints"
```

---

## Task 6: Add audit logs to chat API

**Files:**
- Modify: `backend/app/api/chat.py`

**Step 1: Add structlog import**

```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add log at stream start**

In `chat_stream`, after saving the human message (`await db.commit()`):
```python
logger.info(
    "chat_stream_started",
    user_id=str(user.id),
    conv_id=str(body.conversation_id),
    provider=llm.provider,
    model=llm.model_name,
)
```

**Step 3: Add logs inside generate()**

In the `generate()` async generator, replace the existing body with:
```python
async def generate() -> AsyncGenerator[str]:
    graph = create_graph(
        provider=llm.provider,
        model=llm.model_name,
        api_key=llm.api_key,
        enabled_tools=llm.enabled_tools,
    )
    full_content = ""
    try:
        async for chunk in graph.astream(AgentState(messages=lc_messages)):
            if "llm" in chunk:
                ai_msg = chunk["llm"]["messages"][-1]
                full_content = ai_msg.content
                data = json.dumps({"content": full_content})
                yield "data: " + data + "\n\n"
    except Exception:
        logger.exception("chat_stream_error", conv_id=str(conv_id))
        raise

    async with AsyncSessionLocal() as session:
        async with session.begin():
            session.add(
                Message(
                    conversation_id=conv_id,
                    role="ai",
                    content=full_content,
                    model_provider=llm.provider,
                    model_name=llm.model_name,
                )
            )
    logger.info("chat_stream_completed", conv_id=str(conv_id), response_chars=len(full_content))
```

**Step 4: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "feat: add audit logs to chat stream endpoint"
```

---

## Task 7: Add audit logs to documents API

**Files:**
- Modify: `backend/app/api/documents.py`

**Step 1: Add structlog import**

```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add log after successful upload**

In `upload_document`, after `await db.commit()`, before `return`:
```python
logger.info(
    "document_uploaded",
    user_id=str(user.id),
    doc_id=str(doc.id),
    filename=doc.filename,
    file_type=ext,
    file_size_bytes=len(content),
    chunk_count=chunk_count,
)
```

**Step 3: Check for delete endpoint**

`documents.py` currently has no delete endpoint. Skip delete log for now — it can be added when the endpoint is built.

**Step 4: Commit**

```bash
git add backend/app/api/documents.py
git commit -m "feat: add audit logs to documents upload endpoint"
```

---

## Task 8: Add audit logs to settings API

**Files:**
- Modify: `backend/app/api/settings.py`

**Step 1: Add structlog import**

```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add log to update_settings**

In `update_settings`, after `await db.commit()`:
```python
logger.info(
    "settings_updated",
    user_id=str(user.id),
    model_provider=body.model_provider,
    model_name=body.model_name,
    api_keys_updated=body.api_keys is not None,
    persona_updated=body.persona_override is not None,
)
```

Note: never log `api_keys` values — only log whether they were updated.

**Step 3: Commit**

```bash
git add backend/app/api/settings.py
git commit -m "feat: add audit logs to settings endpoint"
```

---

## Task 9: Add Agent execution logs

**Files:**
- Modify: `backend/app/agent/graph.py`

**Step 1: Add structlog import**

```python
import structlog

logger = structlog.get_logger(__name__)
```

**Step 2: Add logs inside call_llm**

Replace the existing `call_llm` function:
```python
async def call_llm(state: AgentState) -> dict[str, list[BaseMessage]]:
    response = await llm_with_tools.ainvoke(state.messages)
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        logger.info("agent_tool_calls", tools=tool_names)
    else:
        logger.info("agent_llm_response", content_chars=len(str(response.content)))
    return {"messages": [response]}
```

**Step 3: Commit**

```bash
git add backend/app/agent/graph.py
git commit -m "feat: add audit logs to LangGraph agent"
```

---

## Task 10: Create client error reporting endpoint

**Files:**
- Create: `backend/app/api/logs.py`
- Modify: `backend/app/main.py`

**Step 1: Create the endpoint**

```python
"""Client-side error reporting endpoint."""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ClientError(BaseModel):
    message: str
    source: str | None = None
    trace_id: str | None = None
    url: str | None = None
    stack: str | None = None


@router.post("/client-error", status_code=204)
async def report_client_error(body: ClientError) -> None:
    """Accept and log client-side errors. No auth required (errors happen before auth)."""
    logger.warning(
        "client_error",
        message=body.message[:500],  # truncate to prevent log flooding
        source=body.source,
        trace_id=body.trace_id,
        url=body.url,
    )
```

**Step 2: Register router in main.py**

In `backend/app/main.py`:

1. Add import:
```python
from app.api.logs import router as logs_router
```

2. Add after other `app.include_router(...)` calls:
```python
app.include_router(logs_router)
```

**Step 3: Commit**

```bash
git add backend/app/api/logs.py backend/app/main.py
git commit -m "feat: add client error reporting endpoint"
```

---

## Task 11: Add .env LOG_LEVEL variable

**Files:**
- Modify: `.env.example` (root of repo)
- Modify: `.env` (root of repo, not tracked by git — add manually if it exists)

**Step 1: Update .env.example**

Find the section with other non-sensitive config vars in `.env.example` and add:
```bash
# Logging
LOG_LEVEL=INFO
```

**Step 2: Add to local .env**

```bash
grep -q "LOG_LEVEL" .env || echo "" >> .env && echo "LOG_LEVEL=INFO" >> .env
```

**Step 3: Commit**

```bash
git add .env.example
git commit -m "chore: add LOG_LEVEL to env config"
```

---

## Task 12: Add Docker log rotation to all containers

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add logging config to every service**

For each service in `docker-compose.yml` (postgres, qdrant, redis, minio, minio-init, backend, frontend, traefik, cadvisor, postgres_exporter, redis_exporter, prometheus, grafana), add:

```yaml
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Place it after the `restart:` line for each service. `minio-init` uses `restart: "no"` — still add logging config.

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add Docker log rotation to all containers"
```

---

## Task 13: Create Loki configuration

**Files:**
- Create: `monitoring/loki/loki-config.yaml`

**Step 1: Create the config**

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2025-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 168h   # 7 days

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h

ruler:
  alertmanager_url: http://localhost:9093
```

**Step 2: Commit**

```bash
git add monitoring/loki/loki-config.yaml
git commit -m "feat: add Loki configuration (7-day retention)"
```

---

## Task 14: Create Promtail configuration

**Files:**
- Create: `monitoring/promtail/promtail-config.yaml`

**Step 1: Create the config**

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /promtail-data/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker-containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: [__meta_docker_container_name]
        regex: /(.*)
        target_label: container
      - source_labels: [__meta_docker_container_label_com_docker_compose_service]
        target_label: service
      - source_labels: [__meta_docker_container_label_com_docker_compose_project]
        target_label: project
    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
      - output:
          source: log
```

**Step 2: Commit**

```bash
git add monitoring/promtail/promtail-config.yaml
git commit -m "feat: add Promtail configuration for Docker log collection"
```

---

## Task 15: Add Loki datasource to Grafana

**Files:**
- Create: `monitoring/grafana/provisioning/datasources/loki.yaml`

**Step 1: Create the datasource**

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: false
    editable: false
    jsonData:
      maxLines: 1000
```

**Step 2: Commit**

```bash
git add monitoring/grafana/provisioning/datasources/loki.yaml
git commit -m "feat: add Loki datasource to Grafana provisioning"
```

---

## Task 16: Add Grafana logs dashboard

**Files:**
- Create: `monitoring/grafana/provisioning/dashboards/logs.json`
- Check: `monitoring/grafana/provisioning/provider.yml` (must include dashboards path)

**Step 1: Check existing provider.yml**

```bash
cat monitoring/grafana/provisioning/provider.yml
```

If it doesn't exist or doesn't reference dashboards, create/update `monitoring/grafana/provisioning/dashboards/provider.yml`:

```yaml
apiVersion: 1

providers:
  - name: default
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Step 2: Create minimal logs dashboard**

Create `monitoring/grafana/provisioning/dashboards/logs.json`:

```json
{
  "__inputs": [],
  "__elements": {},
  "__requires": [
    {"type": "datasource", "id": "loki", "name": "Loki", "version": "1.0.0"}
  ],
  "annotations": {"list": []},
  "description": "JARVIS Application Logs",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "loki", "uid": "${datasource}"},
      "gridPos": {"h": 4, "w": 24, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "dedupStrategy": "none",
        "enableLogDetails": true,
        "prettifyLogMessage": false,
        "showCommonLabels": false,
        "showLabels": false,
        "showTime": true,
        "sortOrder": "Descending",
        "wrapLogMessage": false
      },
      "targets": [
        {
          "datasource": {"type": "loki", "uid": "${datasource}"},
          "expr": "{service=~\"$service\"} |= `$search`",
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "All Logs",
      "type": "logs"
    },
    {
      "datasource": {"type": "loki", "uid": "${datasource}"},
      "gridPos": {"h": 4, "w": 24, "x": 0, "y": 4},
      "id": 2,
      "options": {
        "dedupStrategy": "none",
        "enableLogDetails": true,
        "prettifyLogMessage": false,
        "showCommonLabels": false,
        "showLabels": false,
        "showTime": true,
        "sortOrder": "Descending",
        "wrapLogMessage": false
      },
      "targets": [
        {
          "datasource": {"type": "loki", "uid": "${datasource}"},
          "expr": "{service=~\"$service\"} | json | level=`error` or level=`warning`",
          "queryType": "range",
          "refId": "A"
        }
      ],
      "title": "Errors & Warnings",
      "type": "logs"
    }
  ],
  "refresh": "10s",
  "schemaVersion": 39,
  "tags": ["jarvis", "logs"],
  "templating": {
    "list": [
      {
        "current": {},
        "hide": 0,
        "includeAll": false,
        "name": "datasource",
        "options": [],
        "query": "loki",
        "refresh": 1,
        "type": "datasource",
        "label": "Data Source"
      },
      {
        "current": {"selected": true, "text": "All", "value": "$__all"},
        "datasource": {"type": "loki", "uid": "${datasource}"},
        "definition": "label_values(service)",
        "hide": 0,
        "includeAll": true,
        "multi": true,
        "name": "service",
        "query": "label_values(service)",
        "refresh": 2,
        "type": "query",
        "label": "Service"
      },
      {
        "current": {"selected": false, "text": "", "value": ""},
        "hide": 0,
        "name": "search",
        "query": "",
        "type": "textbox",
        "label": "Search"
      }
    ]
  },
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "JARVIS Logs",
  "uid": "jarvis-logs",
  "version": 1
}
```

**Step 3: Commit**

```bash
git add monitoring/grafana/provisioning/dashboards/
git commit -m "feat: add Grafana logs dashboard for Loki"
```

---

## Task 17: Add Loki and Promtail to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add Loki service**

Add after the `prometheus` service block:

```yaml
  loki:
    image: grafana/loki:3.4.2
    networks: [monitor]
    restart: unless-stopped
    command: -config.file=/etc/loki/config.yaml
    volumes:
      - ./monitoring/loki/loki-config.yaml:/etc/loki/config.yaml:ro
      - ${HOME}/jarvis-data/loki:/loki
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3100/ready || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**Step 2: Add Promtail service**

Add after the `loki` service block:

```yaml
  promtail:
    image: grafana/promtail:3.4.2
    networks: [monitor]
    restart: unless-stopped
    command: -config.file=/etc/promtail/config.yaml
    volumes:
      - ./monitoring/promtail/promtail-config.yaml:/etc/promtail/config.yaml:ro
      - ${HOME}/jarvis-data/promtail:/promtail-data
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      loki:
        condition: service_healthy
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Step 3: Update Grafana to depend on Loki**

In the `grafana` service, update `depends_on` or add if not present:

The grafana service currently has no `depends_on`. It's not strictly required since Grafana will retry datasource connections, so no change needed here.

**Step 4: Add backend LOG_LEVEL env var**

In the `backend` service `environment` block, add:
```yaml
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
```

**Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Loki and Promtail services to docker-compose"
```

---

## Task 18: Add frontend global error handler

**Files:**
- Modify: `frontend/src/main.ts`

**Step 1: Add error reporting utility**

In `frontend/src/main.ts`, add a helper after the imports:

```typescript
function reportError(message: string, source: string, stack?: string): void {
  const traceId = document.cookie.match(/X-Trace-ID=([^;]+)/)?.[1];
  fetch("/api/logs/client-error", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: String(message).slice(0, 500),
      source,
      trace_id: traceId ?? null,
      url: window.location.href,
      stack: stack?.slice(0, 1000) ?? null,
    }),
  }).catch(() => {/* best-effort, silently ignore */});
}
```

**Step 2: Register global error handlers**

After `app.mount("#app")`, add:

```typescript
app.config.errorHandler = (err, _instance, info) => {
  console.error("[Vue error]", err, info);
  reportError(String(err), `vue:${info}`);
};

window.onerror = (message, source, lineno, colno, error) => {
  reportError(String(message), `window:${source}:${lineno}:${colno}`, error?.stack);
  return false;
};

window.addEventListener("unhandledrejection", (event) => {
  reportError(String(event.reason), "unhandledrejection", event.reason?.stack);
});
```

**Step 3: Commit**

```bash
git add frontend/src/main.ts
git commit -m "feat: add global error handler and client error reporting"
```

---

## Task 19: Fix silent catch blocks in frontend stores

**Files:**
- Modify: `frontend/src/stores/chat.ts`

**Step 1: Fix deleteConversation catch**

Find the empty `catch` block in `deleteConversation`:

```typescript
      } catch {
        // 删除失败时保持列表不变，静默处理
      }
```

Replace with:
```typescript
      } catch (err) {
        console.error("[chat] deleteConversation failed", err);
      }
```

**Step 2: Fix selectConversation catch**

Find:
```typescript
      } catch {
        this.currentConvId = null;
      }
```

Replace with:
```typescript
      } catch (err) {
        console.error("[chat] selectConversation failed", err);
        this.currentConvId = null;
      }
```

**Step 3: Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "fix: replace silent catch blocks with error logging in chat store"
```

---

## Task 20: Smoke test the full stack

**Step 1: Start all services**

```bash
docker compose up -d
```

Expected: all containers start including `loki` and `promtail`.

**Step 2: Check Loki is healthy**

```bash
curl -s http://localhost:3100/ready
```

Expected: `ready`

**Step 3: Check Promtail is running**

```bash
docker compose logs promtail --tail 20
```

Expected: lines like `"level=info msg="Promtail started"` and targets being scraped.

**Step 4: Check backend logs are JSON**

```bash
docker compose logs backend --tail 5
```

Expected: JSON lines like `{"timestamp": "...", "level": "info", "event": "Infrastructure ready.", ...}`

**Step 5: Open Grafana and verify Loki datasource**

Visit `http://localhost:3001`, log in with admin / `$GRAFANA_PASSWORD`.

Navigate to Connections → Data Sources → confirm "Loki" appears and "Test" passes.

**Step 6: Open Grafana Logs dashboard**

Navigate to Dashboards → JARVIS Logs. Select "backend" service. Confirm log lines appear.

**Step 7: Final commit**

```bash
git add .
git commit -m "chore: verify observability stack smoke test passed"
```

---

## Summary of all new/modified files

| File | Operation |
|------|-----------|
| `backend/pyproject.toml` | Add structlog |
| `backend/app/core/config.py` | Add log_level field |
| `backend/app/core/logging.py` | New — structlog setup |
| `backend/app/core/logging_middleware.py` | New — trace ID middleware |
| `backend/app/main.py` | Wire logging + middleware |
| `backend/app/api/auth.py` | Audit logs |
| `backend/app/api/conversations.py` | Audit logs |
| `backend/app/api/chat.py` | Audit logs |
| `backend/app/api/documents.py` | Audit logs |
| `backend/app/api/settings.py` | Audit logs |
| `backend/app/api/logs.py` | New — client error endpoint |
| `backend/app/agent/graph.py` | Agent execution logs |
| `frontend/src/main.ts` | Global error handler |
| `frontend/src/stores/chat.ts` | Fix silent catch blocks |
| `.env.example` | Add LOG_LEVEL |
| `docker-compose.yml` | Log rotation + Loki + Promtail |
| `monitoring/loki/loki-config.yaml` | New |
| `monitoring/promtail/promtail-config.yaml` | New |
| `monitoring/grafana/provisioning/datasources/loki.yaml` | New |
| `monitoring/grafana/provisioning/dashboards/logs.json` | New |
