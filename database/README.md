# database/ — 存储组件设计与初始化

本目录是所有存储组件（PostgreSQL、Qdrant、MinIO、Redis）的 **设计真相源**。

## 目录结构

```
database/
├── README.md                    # 本文件
├── design/
│   └── schema-design.md         # 全量设计文档（ER 图、索引策略、容量预估）
├── postgres/
│   ├── 01_extensions.sql        # 扩展（pgcrypto）
│   ├── 02_users.sql             # 用户表
│   ├── 03_user_settings.sql     # 用户设置表
│   ├── 04_conversations.sql     # 对话表
│   ├── 05_messages.sql          # 消息表
│   ├── 06_documents.sql         # 文档表
│   └── 07_indexes.sql           # 非主键索引
├── qdrant/
│   └── collections.json         # Collection 定义规范
├── minio/
│   └── buckets.json             # Bucket 定义
└── redis/
    ├── redis.conf               # Redis 配置文件
    └── keyspace-design.md       # Key 命名规范
```

## 各组件初始化方式

| 组件 | 初始化方式 | 说明 |
|------|-----------|------|
| PostgreSQL | `docker-entrypoint-initdb.d` | DDL 文件按文件名排序自动执行（仅首次初始化空数据库时） |
| Qdrant | 后端 lifespan / 业务层 | Collection 按用户动态创建，由 `ensure_user_collection()` 保证幂等 |
| MinIO | `minio-init` 容器（mc client） | docker-compose 中 `minio-init` 服务自动创建 bucket |
| Redis | 配置文件挂载 | `redis.conf` 挂载到容器，通过 `redis-server` 命令加载 |

## 全新部署 vs 增量迁移

### 全新部署

```bash
docker-compose up -d
```

PostgreSQL 容器首次启动时，会自动执行 `database/postgres/*.sql`。其他组件由各自的初始化机制处理。

### 增量迁移（已有数据）

PostgreSQL 的 `docker-entrypoint-initdb.d` **仅在数据库为空时执行**。已有数据的环境需使用 Alembic：

```bash
cd backend
uv run alembic upgrade head
```

## DDL 与 Alembic 的关系

- `database/postgres/*.sql`：**设计参考**，定义了表的目标状态
- `backend/alembic/`：**迁移工具**，管理增量变更

两者需保持同步：修改 DDL 后，必须生成对应的 Alembic migration。

## 新增表 / 改字段的标准操作流程

1. 修改或新增 `database/postgres/*.sql` 中的 DDL
2. 更新 `database/design/schema-design.md` 中的 ER 图和字段说明
3. 修改 `backend/app/db/models.py` 中的 SQLAlchemy 模型
4. 生成 Alembic migration：
   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "描述变更"
   ```
5. 审查生成的 migration 文件
6. 应用 migration：
   ```bash
   uv run alembic upgrade head
   ```
