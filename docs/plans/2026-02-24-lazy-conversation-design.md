# 延迟创建对话设计

## 问题

点击 "New Chat" 后立即在侧边栏创建标题为 "New Chat" 的对话，即使用户还没发任何消息。标题始终是 "New Chat"，没有意义。

## 目标

模仿 ChatGPT/Claude 的行为：
1. 点击 "New Chat" 仅清空聊天区域，不创建对话
2. 用户发送第一条消息时才创建对话，标题取消息前 30 字
3. 新对话此时出现在侧边栏，标题有意义

## 方案

**延迟创建对话**：将对话创建从 `newConversation()` 移到 `sendMessage()` 中。

### 改动范围

**仅前端（2 个文件）：**

| 文件 | 改动 |
|------|------|
| `frontend/src/stores/chat.ts` | `newConversation()` 变为纯本地重置；`sendMessage()` 增加懒创建逻辑 |
| `frontend/src/pages/ChatPage.vue` | `send()` 移除手动 `newConversation()` 调用 |

**后端零改动** — `POST /conversations` 已支持自定义 `title`。

### chat.ts 改动

`newConversation()`：不再调 API，仅重置状态。

```typescript
newConversation() {
  this.currentConvId = null;
  this.messages = [];
}
```

`sendMessage(content)` 开头增加懒创建：

```typescript
if (!this.currentConvId) {
  const title = content.slice(0, 30) + (content.length > 30 ? "..." : "");
  const { data } = await client.post("/conversations", { title });
  this.conversations.unshift(data);
  this.currentConvId = data.id;
}
```

### ChatPage.vue 改动

`send()` 函数简化，移除 `if (!chat.currentConvId) await chat.newConversation()`，因为 `sendMessage` 内部已处理。

### 边界情况

- 空白页直接输入 → `sendMessage` 自动创建对话
- 快速连续发送 → `streaming` 锁阻止重复
- 创建 API 失败 → 无 convId，消息不会发送
