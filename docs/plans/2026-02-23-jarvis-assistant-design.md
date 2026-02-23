# Jarvis 个人助手系统设计文档

**日期**：2026-02-23
**状态**：已批准，待实现

---

## 一、项目目标

构建一个面向多用户的 AI 个人助手系统，类似钢铁侠中的 JARVIS。支持通用对话、工具调用、私有知识库问答（RAG），用户数据完全隔离，通过 Web 界面访问，底层优先使用 DeepSeek，支持多模型切换。

---

## 二、目标用户

- 技术用户（开发者、研究者）
- 普通消费者
- 企业/团队

---

## 三、架构方案

### 选用方案：单体 LangGraph Agent（方案 A）

**切换至多 Agent 架构（方案 B）的明确触发条件（满足任意一条即切换）：**

| 触发条件 | 说明 |
|----------|------|
| 工具数量超过 8 个 | 单 Agent 工具选择准确率会明显下降 |
| 出现角色分离需求 | 如需要专门的代码 Agent、写作 Agent，各自有不同系统提示 |
| 单次请求需要并行处理 | 如同时搜索多个来源、同时调用多个工具，串行太慢 |
| 某个能力需要独立迭代 | 如 RAG 模块频繁升级影响主 Agent 稳定性 |

### 整体架构图

```
用户浏览器（Vue 3 + TypeScript）
    ↓ HTTP / WebSocket
FastAPI 后端
    ├── 用户认证 & 会话管理（JWT）
    ├── LangGraph Agent（核心）
    │     ├── 路由节点（判断意图：纯对话 / 工具 / RAG）
    │     ├── 工具节点（搜索、代码执行、文件读写、日期时间）
    │     ├── RAG 节点（向量检索用户私有文档）
    │     └── LLM 路由（DeepSeek / GPT-4 / Claude 等）
    ├── Qdrant（向量数据库，按用户 namespace 隔离）
    ├── PostgreSQL（用户、对话历史、文件元数据）
    ├── Redis（会话缓存、限流）
    └── MinIO（用户上传文件存储）

语音入口：预留在前端，后端接口保持输入格式通用，后期接入。
```

---

## 四、技术栈

| 层级 | 技术 | Docker 镜像 |
|------|------|------------|
| 前端 | Vue 3 + TypeScript + Vite | `oven/bun:1.3.9`（始终使用最新稳定版） |
| 后端 | FastAPI + Python 3.13 | `python:3.13.12-slim-bookworm` |
| Agent 框架 | LangGraph | 随 uv 管理 |
| 关系数据库 | PostgreSQL 18 | `postgres:18.2-bookworm` |
| 向量数据库 | Qdrant | `qdrant/qdrant:v1.17.0` |
| 缓存 | Redis 8 | `redis:8.6.0-alpine3.23` |
| 文件存储 | MinIO | `minio/minio:RELEASE.2025-09-07T16-13-09Z` |
| 部署 | Docker + Docker Compose | - |

> **Bun 版本策略**：始终使用当时最新稳定版，每次更新 docker-compose.yml 时手动对齐。

---

## 五、核心模块设计

### 5.1 用户系统

- 注册 / 登录，JWT 鉴权
- 每个用户独立拥有：对话历史、上传文件、Qdrant namespace、模型偏好、API Key

### 5.2 LangGraph Agent 流程

```
用户消息
    ↓
[路由节点] 判断意图
    ↓           ↓            ↓
[LLM 节点] [工具调用节点] [RAG 检索节点]
               ↓               ↓
         [工具执行结果] → [合并上下文] → [LLM 生成回答] → 流式返回
```

**初期内置工具（4 个）：**

| 工具 | 说明 |
|------|------|
| 网络搜索 | 实时搜索互联网信息 |
| 代码执行 | 沙箱环境执行代码 |
| 文件读写 | 用户私有文件空间 |
| 日期/时间查询 | 获取当前时间信息 |

### 5.3 RAG 模块

- 支持上传格式：PDF、txt、md、docx
- 流程：上传 → 切片 → 向量化 → 存入 Qdrant（用户独立 namespace）
- 检索时仅查询当前用户 namespace，完全隔离

### 5.4 LLM 路由

- 默认使用 DeepSeek
- 用户可在设置页切换模型（GPT-4、Claude 等）
- 后端统一封装，前端无感知
- 新增模型只需修改路由层

### 5.5 前端页面

| 页面 | 功能 |
|------|------|
| 聊天界面 | 流式输出、对话历史、新建对话 |
| 文件上传页 | 上传文档到知识库 |
| 设置页 | 模型切换、API Key 管理 |
| 语音入口 | 按钮占位，功能后期接入 |

---

## 六、数据库 Schema（PostgreSQL）

```sql
-- 用户表
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 用户设置表（模型偏好、API Key、工具开关）
CREATE TABLE user_settings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_provider  VARCHAR(50) NOT NULL DEFAULT 'deepseek',
    model_name      VARCHAR(100) NOT NULL DEFAULT 'deepseek-chat',
    api_keys        JSONB NOT NULL DEFAULT '{}',
    enabled_tools   JSONB NOT NULL DEFAULT '["search","code_exec","file","datetime"]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id)
);

-- 对话表
CREATE TABLE conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 消息表
CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                VARCHAR(20) NOT NULL CHECK (role IN ('human', 'ai', 'tool', 'system')),
    content             TEXT NOT NULL,
    tool_calls          JSONB,
    model_provider      VARCHAR(50),
    model_name          VARCHAR(100),
    tokens_input        INTEGER,
    tokens_output       INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 用户文档表
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            VARCHAR(255) NOT NULL,
    file_type           VARCHAR(20) NOT NULL CHECK (file_type IN ('pdf', 'txt', 'md', 'docx')),
    file_size_bytes     INTEGER NOT NULL,
    chunk_count         INTEGER NOT NULL DEFAULT 0,
    qdrant_collection   VARCHAR(255) NOT NULL,
    minio_object_key    VARCHAR(500) NOT NULL,
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_documents_user_id ON documents(user_id);
```

Schema 通过 **Alembic** 迁移管理，每次字段变更有版本记录，支持回滚。

---

## 七、Docker Compose 服务结构

```yaml
services:
  postgres:
    image: postgres:18.2-bookworm

  qdrant:
    image: qdrant/qdrant:v1.17.0

  redis:
    image: redis:8.6.0-alpine3.23

  minio:
    image: minio/minio:RELEASE.2025-09-07T16-13-09Z

  backend:
    build: ./backend   # python:3.13.12-slim-bookworm
    depends_on: [postgres, qdrant, redis, minio]

  frontend:
    build: ./frontend  # oven/bun:1.3.9（始终最新稳定版）
    depends_on: [backend]
```

---

## 八、错误处理策略

| 场景 | 处理方式 |
|------|----------|
| LLM 调用失败 | 自动重试 1 次，失败后返回友好提示，不暴露内部错误 |
| 工具执行超时 | 30 秒超时限制，超时告知用户 |
| 文件上传过大 | 前端限制 50MB，超出提示用户 |
| API Key 无效 | 立即返回明确错误，引导至设置页修改 |

---

## 九、测试策略

- **单元测试**：每个工具节点、RAG 检索逻辑
- **集成测试**：完整 Agent 图端到端流程
- **暂不做**：UI 自动化测试（早期成本过高）

---

## 十、后期扩展预留

- **语音交互**：前端按钮占位，后端输入接口保持格式通用
- **多 Agent 架构**：满足第三节触发条件时切换
- **移动端**：Web 响应式设计，为后期 App 预留 API
