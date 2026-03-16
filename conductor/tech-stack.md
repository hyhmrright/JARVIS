# 技术栈 (Tech Stack)

## 后端 (Backend)
- **语言**：Python 3.13+
- **框架**：FastAPI (异步 Web 框架)，LangGraph (智能体编排)，LangChain (LLM 链式处理)，langchain-ollama (本地模型支持)。
- **数据库 ORM**：SQLAlchemy 2.0+ (异步)。
- **迁移工具**：Alembic。
- **校验与设置**：Pydantic v2+, Pydantic-Settings。
- **并发控制**：Asyncio, Asyncpg。
- **自动化调度**：APScheduler。
- **消息适配器**：aiogram (Telegram), slack-bolt (Slack), discord.py (Discord)。
- **沙箱环境**：Python Docker SDK, Playwright (Chromium)。

## 前端 (Frontend)
- **框架**：Vue 3 (Composition API)。
- **构建工具**：Vite。
- **语言**：TypeScript 5+。
- **状态管理**：Pinia。
- **样式**：Tailwind CSS (v4+), Custom CSS。
- **UI 组件库**：Radix Vue, Lucide Vue Next。
- **数据可视化**：ECharts。
- **网络请求**：Axios。

## 基础设施 (Infrastructure)
- **数据库**：PostgreSQL (关系型数据库)。
- **缓存**：Redis (键值对缓存，hiredis 支持)。
- **向量存储**：Qdrant (RAG 向量索引)。
- **对象存储**：MinIO (文件存储)。
- **边缘网关**：Traefik。
- **监控**：Prometheus, Grafana, Loki, Promtail。

## 开发与质量 (Dev & Quality)
- **后端 Linting**：Ruff。
- **后端型检查**：Mypy。
- **后端测试**：Pytest (覆盖率分析)。
- **前端工具**：Bun (依赖管理)，ESLint, Vue-TSC (类型检查)。
- **持续集成**：GitHub Actions (预先配置的 pre-commit 钩子)。
