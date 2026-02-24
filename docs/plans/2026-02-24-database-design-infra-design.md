# 数据库设计文档化 & 基础设施初始化重构

**日期**：2026-02-24
**状态**：已批准，待实现

---

## 一、背景与目标

当前数据库 schema 散落在 Alembic 迁移文件、ORM 模型和设计文档中，DBA 无法独立工作。Qdrant Collection 和 MinIO Bucket 的创建逻辑硬编码在业务代码中，每次请求都执行存在性检查，浪费资源。Redis 无 Key 设计规范。

**目标**：
1. 建立 `database/` 目录，用专业 DBA 友好的格式管理所有存储组件的设计
2. 按各组件官方推荐方式实现 Docker Compose 自动初始化
3. 后端新增 `infra/` 模块，统一管理基础设施客户端和初始化

---

## 二、调研结论

| 组件 | 官方推荐初始化方式 | 内置 init 机制 |
|------|-------------------|---------------|
| PostgreSQL | 挂载 `.sql` 到 `/docker-entrypoint-initdb.d/`，首次启动按文件名字母序执行 | 有 |
| Qdrant | 无 init hook，Collection 须通过 API 创建；配置通过 YAML + 环境变量 | 无 |
| MinIO | `mc`（MinIO Client）init 容器模式：单独服务执行 `mc mb` 后退出 | 无 |
| Redis | 挂载 `redis.conf` 自定义配置；无 schema 概念 | 仅配置文件 |

---

## 三、目录结构

```
database/
├── README.md                           # 使用指南：各组件初始化方式、维护流程
├── design/
│   └── schema-design.md                # 全量设计文档（ER、字段说明、索引、约束、容量预估）
├── postgres/
│   ├── 01_extensions.sql               # pgcrypto 等扩展
│   ├── 02_users.sql
│   ├── 03_user_settings.sql
│   ├── 04_conversations.sql
│   ├── 05_messages.sql
│   ├── 06_documents.sql
│   └── 07_indexes.sql
├── qdrant/
│   └── collections.json                # Collection 定义（向量维度、距离算法、payload 索引）
├── redis/
│   ├── redis.conf                      # 自定义配置（持久化策略、内存限制）
│   └── keyspace-design.md              # Key 命名规范、数据结构、TTL
└── minio/
    └── buckets.json                    # Bucket 名称、策略
```

---

## 四、初始化策略

| 组件 | 初始化方式 | 触发时机 |
|------|-----------|---------|
| PostgreSQL | docker-compose 挂载 `database/postgres/` → `/docker-entrypoint-initdb.d/` | 首次启动（数据目录为空时） |
| Qdrant | 后端 lifespan 调用 API 创建 Collection（幂等），配置读自 `collections.json` | 每次启动检查 |
| MinIO | docker-compose 新增 `minio-init` 服务，用 mc 镜像创建 Bucket 后退出 | 首次启动 |
| Redis | docker-compose 挂载 `redis.conf`，传给 `redis-server` | 每次启动 |

---

## 五、docker-compose 变更

### PostgreSQL — 新增 init 脚本挂载
```yaml
postgres:
  volumes:
    - ${HOME}/jarvis-data/postgres:/var/lib/postgresql/18/docker
    - ./database/postgres:/docker-entrypoint-initdb.d:ro    # 新增
```

### Redis — 新增自定义配置
```yaml
redis:
  volumes:
    - ${HOME}/jarvis-data/redis:/data
    - ./database/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
  command: redis-server /usr/local/etc/redis/redis.conf
```

### MinIO Init — 全新服务
```yaml
minio-init:
  image: quay.io/minio/mc:latest
  depends_on:
    minio:
      condition: service_healthy
  restart: "no"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  entrypoint: /bin/sh -c "
    mc alias set jarvis http://minio:9000 $$MINIO_ROOT_USER $$MINIO_ROOT_PASSWORD;
    mc mb --ignore-existing jarvis/jarvis-documents;
    exit 0;
    "
```

---

## 六、后端代码变更

### 新增 `backend/app/infra/` 模块
```
backend/app/infra/
├── __init__.py
├── qdrant.py       # get_client() + ensure_collections()
├── minio.py        # get_client()
└── redis.py        # get_client()
```

### 改动现有文件
- `main.py`：lifespan 中调用 `qdrant.ensure_collections()`
- `rag/indexer.py`：删除内联 collection 创建逻辑，改用 `infra.qdrant.get_client()`
- `api/documents.py`：删除内联 bucket 检查逻辑，改用 `infra.minio.get_client()`

---

## 七、Alembic 与 DDL 文件的关系

| 场景 | 使用什么 |
|------|---------|
| 全新部署（docker-compose up 首次） | PostgreSQL 自动执行 `database/postgres/*.sql` |
| 已有数据库增量变更 | Alembic 迁移（`alembic upgrade head`） |
| DBA 评审设计 | 阅读 `database/design/schema-design.md` + `postgres/*.sql` |
| 新增表/改字段 | 先改 DDL → 再写 Alembic 迁移 → 再改 ORM 模型 |

DDL 文件是**设计真相源**，Alembic 是**运行时迁移工具**，两者并行维护。
