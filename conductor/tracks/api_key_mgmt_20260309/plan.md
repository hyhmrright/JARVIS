# 实施计划: 实现用户 API 密钥管理 (Implement User API Key Management)

## Phase 1: 后端模型与数据库 (Backend Models & Database)
- [x] Task: 定义 \`APIKey\` 模型和 Alembic 迁移 (Define APIKey model & migrations) [264565f]
- [x] Task: 实现密钥生成逻辑和哈希处理 (Implement key generation & hashing logic) [a922ec2]
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md) [checkpoint: d21aa17]

## Phase 2: 后端 API 端点 (Backend API Endpoints)
- [x] Task: 实现创建、列举和删除 API 密钥的端点 (Implement CRUD endpoints for API keys) [1133d10]
- [x] Task: 为新端点编写测试 (Write tests for new endpoints) [1133d10]
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md) [checkpoint: aa53b64]

## Phase 3: 身份验证中间件 (Authentication Middleware)
- [x] Task: 实现 API 密钥身份验证装饰器/依赖项 (Implement API key auth dependency) [c4521b4]
- [x] Task: 验证 API 密钥在受保护端点上的工作情况 (Verify key auth on protected endpoints) [c4521b4]
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: 前端界面 (Frontend Interface)
- [ ] Task: 创建 API 密钥管理面板 (Create API key management panel)
- [ ] Task: 集成 API 端点并在前端显示状态 (Integrate API endpoints & show state)
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
