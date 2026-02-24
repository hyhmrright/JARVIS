# Redis Key 命名规范

## 命名格式

`jarvis:{domain}:{identifier}:{sub_key}`

## Key 清单

| Key 模式 | 数据结构 | TTL | 说明 |
|----------|---------|-----|------|
| `jarvis:session:{user_id}` | STRING (JSON) | 7d | 用户会话缓存 |
| `jarvis:rate:{user_id}:{endpoint}` | STRING (counter) | 1min | API 限流计数器（slowapi 自动管理） |
| `jarvis:chat:history:{conversation_id}` | LIST | 24h | 近期对话缓存，加速上下文加载 |

## 约定

- 所有 Key 以 `jarvis:` 开头，避免与其他服务冲突
- TTL 必须设置，禁止无过期 Key（防止内存泄漏）
- 生产环境通过环境变量覆盖 maxmemory
