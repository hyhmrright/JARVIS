# Track: 实现用户 API 密钥管理 (Implement User API Key Management)

## 目标 (Goals)
- 允许用户在个人中心生成、查看和撤回 API 密钥。
- 确保 API 密钥的安全存储（哈希处理）。
- 提供基于 API 密钥的身份验证机制。

## 功能要求 (Requirements)
- **后端**：
  - 定义 API 密钥数据模型。
  - 实现生成、列举、撤销 API 密钥的端点。
  - 实现 `APIKeyHeader` 身份验证方案。
- **前端**：
  - 在设置页面中添加 “API 密钥” 管理面板。
  - 支持显示（一次性）新生成的密钥。
  - 支持管理现有密钥。

## 约束 (Constraints)
- 密钥生成后仅能查看一次（明文形式）。
- 密钥必须通过 `bcrypt` 或类似算法哈希存储。
