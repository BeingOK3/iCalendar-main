# 对话上下文记忆功能说明

## 功能概述

本项目的AI助手支持对话上下文记忆功能，能够记住同一会话中的历史对话，实现更智能的多轮对话。

## 实现原理

### 1. 技术架构

- **存储方式**: 使用Python的`collections.deque`数据结构进行内存存储
- **会话隔离**: 基于`session_id`实现多用户/多会话隔离
- **容量限制**: 每个会话最多保存20条消息（可配置）
- **上下文传递**: 每次请求时将最近10条历史消息发送给DeepSeek API

### 2. 核心数据结构

```python
from collections import deque
from typing import Dict, Deque

# 全局对话历史存储：{会话ID: 消息队列}
conversation_history: Dict[str, Deque[dict]] = {}

# 每个会话最多保存的消息数量
MAX_HISTORY_LENGTH = 20
```

每条消息的格式：
```python
{
    "role": "user",      # 或 "assistant"
    "content": "消息内容",
    "timestamp": "2024-01-01T10:00:00"
}
```

### 3. 工作流程

```
用户发送消息
    ↓
获取该会话的历史记录（最近10条）
    ↓
将历史记录 + 当前消息发送给DeepSeek API
    ↓
获取AI回复
    ↓
保存用户消息和AI回复到历史记录
    ↓
返回结果给用户
```

## 核心函数说明

### 1. `get_conversation_history(session_id: str)`

**功能**: 获取指定会话的对话历史队列

**参数**: 
- `session_id`: 会话ID，默认为"default"

**返回**: 
- `Deque[dict]`: 该会话的消息队列（自动创建不存在的会话）

**示例**:
```python
history = get_conversation_history("user_123")
```

---

### 2. `add_to_history(session_id: str, role: str, content: str)`

**功能**: 向指定会话添加一条消息

**参数**:
- `session_id`: 会话ID
- `role`: 消息角色（"user" 或 "assistant"）
- `content`: 消息内容

**特性**:
- 自动添加时间戳
- 当队列超过`MAX_HISTORY_LENGTH`时，自动移除最早的消息

**示例**:
```python
add_to_history("user_123", "user", "明天提醒我开会")
add_to_history("user_123", "assistant", "好的，我已为您设置提醒")
```

---

### 3. `clear_history(session_id: str)`

**功能**: 清空指定会话的对话历史

**参数**:
- `session_id`: 会话ID

**示例**:
```python
clear_history("user_123")  # 清空user_123的所有对话记录
```

---

### 4. `get_history_for_api(session_id: str, max_messages: int = 10)`

**功能**: 获取格式化后的历史记录，用于发送给DeepSeek API

**参数**:
- `session_id`: 会话ID
- `max_messages`: 最多返回的消息数量（默认10条）

**返回**:
- `List[dict]`: 格式化的消息列表，格式符合DeepSeek API要求

**示例**:
```python
history_for_api = get_history_for_api("user_123", max_messages=10)
# 返回: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
```

## API接口说明

### 1. 清空对话历史

**端点**: `DELETE /api/conversation/clear`

**参数**:
- `session_id` (query): 会话ID，默认为"default"

**响应**:
```json
{
    "success": true,
    "message": "Conversation history cleared"
}
```

**示例**:
```bash
curl -X DELETE "http://localhost:8000/api/conversation/clear?session_id=default"
```

---

### 2. 获取对话历史

**端点**: `GET /api/conversation/history`

**参数**:
- `session_id` (query): 会话ID，默认为"default"

**响应**:
```json
{
    "session_id": "default",
    "history": [
        {
            "role": "user",
            "content": "明天下午3点开会",
            "timestamp": "2024-01-01T10:00:00"
        },
        {
            "role": "assistant",
            "content": "好的，我已为您创建一个会议...",
            "timestamp": "2024-01-01T10:00:05"
        }
    ]
}
```

**示例**:
```bash
curl "http://localhost:8000/api/conversation/history?session_id=default"
```

## 使用示例

### 场景1：多轮对话

```
用户: "明天下午3点开会"
AI: "好的，我已为您创建一个会议，时间是明天下午3点"

用户: "把它改到4点"  ← 这里的"它"会被AI理解为刚才创建的会议
AI: "好的，我已将会议时间改为明天下午4点"
```

### 场景2：上下文理解

```
用户: "查看本周的日程"
AI: "本周有以下日程：1. 周一下午3点会议 2. 周三上午10点讨论会..."

用户: "删除第一个"  ← AI会记住"第一个"指的是"周一下午3点会议"
AI: "好的，我已删除周一下午3点的会议"
```

## 前端集成

### JavaScript调用示例

```javascript
// 发送消息时会自动携带历史记录
async function sendMessage(message) {
    const response = await fetch('/api/nl/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: message,
            session_id: 'default'  // 会话ID
        })
    });
    // 服务器端自动处理历史记录的保存和检索
}

// 清除对话历史
async function clearChat() {
    await fetch('/api/conversation/clear?session_id=default', {
        method: 'DELETE'
    });
    // 同时清除前端显示的消息
    chatMessages.innerHTML = '...';
}
```

## 配置说明

### 调整历史记录数量

在`web_client/app.py`中修改以下常量：

```python
# 每个会话最多保存的消息数量
MAX_HISTORY_LENGTH = 20  # 增大此值可保存更多历史

# 在execute_natural_language()函数中修改传递给API的消息数量
history = get_history_for_api(session_id, max_messages=10)  # 可改为15、20等
```

### 会话ID管理

当前默认使用`session_id="default"`，适用于单用户场景。如需支持多用户：

1. 前端生成唯一会话ID（如用户ID、UUID等）
2. 在每次请求时传递`session_id`参数
3. 不同会话的对话历史完全隔离

```javascript
// 示例：使用用户ID作为会话ID
const sessionId = getCurrentUserId(); // 自定义函数获取用户ID
await fetch('/api/nl/execute', {
    method: 'POST',
    body: JSON.stringify({
        query: message,
        session_id: sessionId  // 使用用户专属的session_id
    })
});
```

## 注意事项与限制

### 1. 内存存储
- ⚠️ **重启丢失**: 对话历史保存在内存中，服务器重启后会丢失所有历史记录
- ⚠️ **内存占用**: 大量会话可能占用较多内存

### 2. 容量限制
- 每个会话最多保存20条消息（可配置）
- 超出限制后自动删除最早的消息

### 3. 上下文长度
- 默认只将最近10条消息发送给DeepSeek API
- 过长的上下文可能影响响应速度和API成本

### 4. 会话隔离
- 不同`session_id`的对话完全隔离
- 确保前端正确传递`session_id`以保证对话连贯性

## 未来改进方向

如需更强大的功能，可考虑以下升级方案：

1. **持久化存储**: 
   - 使用Redis/数据库存储对话历史
   - 支持服务器重启后恢复历史记录

2. **更智能的上下文管理**:
   - 实现重要消息优先级机制
   - 自动压缩历史对话，提取关键信息

3. **用户认证与授权**:
   - 集成OAuth/JWT身份验证
   - 为每个用户自动分配独立会话

4. **对话分析**:
   - 统计用户使用频率
   - 分析常见问题，优化AI回复

## 常见问题

### Q: 如何验证上下文记忆是否生效？

**A**: 进行以下测试：
```
1. 发送: "明天下午3点开会"
2. 发送: "把它改到4点"  ← 如果AI能理解"它"指的是刚才的会议，说明上下文生效
```

### Q: 清除对话后是否需要刷新页面？

**A**: 不需要，清除操作会同时清理前端和后端的历史记录。

### Q: 多个浏览器窗口会共享对话历史吗？

**A**: 当前默认使用`session_id="default"`，所有窗口共享历史。如需隔离，请为每个窗口生成唯一的`session_id`。

### Q: 如何查看当前的对话历史？

**A**: 调用API接口：
```bash
curl "http://localhost:8000/api/conversation/history?session_id=default"
```

## 代码位置

所有与上下文记忆相关的代码位于：
- **后端**: `web_client/app.py`
  - 第51-130行: 对话历史管理函数
  - 第391-550行: `execute_natural_language()`函数（集成上下文）
  - 第750-780行: 对话历史API接口

- **前端**: `web_client/static/js/app.js`
  - 第264-285行: `clearChat()`函数（清除历史）
  - 第50-90行: `sendMessage()`函数（自动携带session_id）

---

**文档版本**: v1.0  
**最后更新**: 2024  
**作者**: iCalendar Project Team
