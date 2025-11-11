# 上下文记忆功能测试报告

## 📋 已完成的改进

### 1. **核心功能实现**

#### 后端改进 (`web_client/app.py`)
- ✅ 添加了对话历史管理系统（使用 `collections.deque`）
- ✅ 实现了 4 个核心函数（带详细中文注释）
- ✅ 修改了 `execute_natural_language()` 函数的执行流程
- ✅ 新增了 2 个 API 接口（清除历史、获取历史）

#### DeepSeek 客户端改进 (`mcp_ical/deepseek_client.py`)
- ✅ 修改 `parse_calendar_command()` 函数支持对话历史
- ✅ 历史消息会被添加到 API 调用的消息列表中
- ✅ 添加了日志记录，便于调试

#### 前端改进 (`web_client/static/js/app.js`)
- ✅ 修改了 `clearChat()` 函数，同时清除前端和后端历史

### 2. **关键改进点**

#### 🔧 问题 1: 对话历史传递方式
**原问题**: 最初将历史放在 `context["conversation_history"]` 中，但 DeepSeek API 需要直接在消息列表中传递历史。

**解决方案**: 
```python
# mcp_ical/deepseek_client.py 第 120-133 行
messages = [{"role": "system", "content": system_prompt}]

# 如果上下文中包含对话历史，添加到消息列表中
conversation_history = context.get("conversation_history", [])
if conversation_history:
    messages.extend(conversation_history)
    logger.info(f"Added {len(conversation_history)} historical messages to API call")

# 添加当前用户输入
messages.append({"role": "user", "content": user_prompt})
```

#### 🔧 问题 2: 消息保存时机
**原问题**: 在解析命令之前就保存了用户消息，可能导致解析失败时也保存了无效消息。

**解决方案**:
```python
# web_client/app.py 第 452-471 行
# 1. 先获取历史（不包含当前消息）
history_messages = get_history_for_api(session_id, max_messages=10)

# 2. 将历史添加到上下文
context["conversation_history"] = history_messages

# 3. 解析命令（当前用户输入会在 DeepSeek 客户端中添加）
parsed = await deepseek_client.parse_calendar_command(request.text, context)

# 4. 解析成功后，才保存当前用户消息到历史
add_to_history(session_id, "user", request.text)
```

### 3. **工作流程**

```
用户发送消息: "明天下午3点开会"
    ↓
1. 获取该会话的历史记录（最近10条）
   history_messages = get_history_for_api(session_id, max_messages=10)
    ↓
2. 将历史添加到上下文
   context["conversation_history"] = history_messages
    ↓
3. 在 DeepSeek 客户端中构建完整消息列表
   messages = [
       {"role": "system", "content": system_prompt},
       ...history_messages,  # 历史对话
       {"role": "user", "content": "明天下午3点开会"}  # 当前输入
   ]
    ↓
4. 调用 DeepSeek API 获取解析结果
    ↓
5. 解析成功后，保存用户消息
   add_to_history(session_id, "user", "明天下午3点开会")
    ↓
6. 执行相应操作（创建事件、查询等）
    ↓
7. 保存助手回复
   add_to_history(session_id, "assistant", "已创建事件...")
    ↓
返回结果给用户
```

## 🧪 手动测试步骤

### 前置条件
1. 启动服务器：
```bash
cd /Users/hushuai/Desktop/项目/iCalendar-main
uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 --reload
```

2. 打开浏览器访问 `http://localhost:8000`

### 测试场景 1: 代词引用（上下文理解）

**步骤 1**: 在聊天框输入
```
明天下午3点开会
```

**期望结果**: AI 成功创建事件，回复类似 "已创建事件: 会议"

**步骤 2**: 紧接着输入
```
把它改到4点
```

**期望结果**: 
- ✅ **成功**: AI 理解"它"指的是刚才创建的会议，成功修改时间
- ❌ **失败**: AI 提示不知道"它"指什么

**验证方式**: 查看服务器日志
```
2025-11-11 18:48:XX | INFO | web_client.app:execute_natural_language:469 - Using 2 historical messages for context
2025-11-11 18:48:XX | INFO | mcp_ical.deepseek_client:parse_calendar_command:133 - Added 2 historical messages to API call
```

### 测试场景 2: 多轮对话记忆

**步骤 1**: 输入
```
查看本周的日程
```

**步骤 2**: 输入
```
刚才查到几个事件？
```

**期望结果**: AI 能够记住上一次查询的结果并回答

### 测试场景 3: 清除历史

**步骤 1**: 点击界面上的"清除对话"按钮

**步骤 2**: 输入
```
我刚才问了什么？
```

**期望结果**: AI 回复没有历史记录或不知道

**验证方式**: 通过 API 检查历史是否已清除
```bash
curl "http://localhost:8000/api/conversation/history?session_id=default"
```

应返回空的历史记录：
```json
{
  "session_id": "default",
  "history": []
}
```

### 测试场景 4: 会话隔离

**步骤 1**: 打开两个不同的浏览器窗口或标签页

**步骤 2**: 在窗口1中输入
```
明天下午3点开会
```

**步骤 3**: 在窗口2中输入
```
我刚才说了什么？
```

**期望结果**: 
- 如果使用相同 `session_id`（当前默认为"default"）: 窗口2能看到窗口1的历史
- 如果使用不同 `session_id`: 窗口2看不到窗口1的历史

## 🐛 已知问题与改进建议

###问题 1: DeepSeek API 可能不理解代词
**描述**: 即使传递了历史记录，DeepSeek 的 JSON 模式可能限制了上下文理解能力。

**可能原因**:
- DeepSeek API 使用了 `"response_format": {"type": "json_object"}`
- JSON 模式可能限制了模型的推理能力

**改进建议**:
1. **方案 A**: 在前端或后端预处理代词
   - 检测到代词（如"它"、"刚才的"等）时
   - 从历史中提取最后一个事件的详细信息
   - 将代词替换为具体内容："把它改到4点" → "把明天下午3点的会议改到4点"

2. **方案 B**: 使用两步解析
   ```python
   # 第一步：不使用 JSON 模式，让 AI 理解上下文并重写用户输入
   rewritten_query = await deepseek_client.rewrite_with_context(
       user_input, 
       conversation_history
   )
   # 输出: "把明天下午3点的会议改到4点"
   
   # 第二步：使用 JSON 模式解析重写后的查询
   parsed = await deepseek_client.parse_calendar_command(
       rewritten_query, 
       context
   )
   ```

3. **方案 C**: 在 `_build_user_prompt()` 中添加更多上下文提示
   ```python
   def _build_user_prompt(self, user_input, current_time, context):
       prompt = f"用户输入: {user_input}\n\n"
       
       # 如果有对话历史，添加明确的上下文信息
       if "conversation_history" in context:
           recent_events = self._extract_events_from_history(
               context["conversation_history"]
           )
           if recent_events:
               prompt += "最近讨论的事件:\n"
               for event in recent_events:
                   prompt += f"- {event['title']} 在 {event['start_time']}\n"
               prompt += "\n"
       
       prompt += "当前时间: " + current_time.strftime('%Y-%m-%d %H:%M:%S') + "\n"
       # ...
   ```

### 问题 2: 历史记录格式
**描述**: 当前只保存原始的用户输入和 AI 回复，没有保存结构化的事件信息。

**改进建议**: 保存更详细的上下文
```python
{
    "role": "user",
    "content": "明天下午3点开会",
    "timestamp": "2025-11-11T18:00:00",
    "parsed_action": "create_event",  # 新增
    "event_info": {  # 新增
        "title": "会议",
        "start_time": "2025-11-12T15:00:00",
        "event_id": "xxx"
    }
}
```

### 问题 3: 内存存储限制
**描述**: 当前使用内存存储，服务器重启后历史记录会丢失。

**改进建议**: 
1. 添加 Redis 持久化（生产环境）
2. 添加文件缓存（开发环境）
3. 添加数据库存储（完整解决方案）

## 📊 测试验证清单

### ✅ 已验证的功能
- [x] 后端对话历史管理函数正常工作
- [x] 历史消息能够传递到 DeepSeek 客户端
- [x] 清除历史 API 端点可用
- [x] 获取历史 API 端点可用
- [x] 前端清除按钮调用后端 API

### ⏳ 待验证的功能
- [ ] DeepSeek API 实际能否理解代词引用
- [ ] 多轮对话中的上下文准确性
- [ ] 长对话（超过10条消息）的性能
- [ ] 会话隔离功能
- [ ] 并发请求下的历史记录一致性

## 🎯 下一步行动

### 立即可做
1. **手动测试**: 按照上述测试场景在浏览器中进行测试
2. **查看日志**: 观察服务器日志中的历史消息传递情况
3. **调整参数**: 根据测试结果调整 `MAX_HISTORY_LENGTH` 和传递给 API 的消息数量

### 短期改进
1. **实现代词预处理**: 在前端或后端识别并替换代词
2. **增强日志**: 添加更详细的调试信息
3. **用户反馈**: 在 UI 中显示当前对话轮数或历史条数

### 长期改进
1. **持久化存储**: 使用 Redis 或数据库
2. **智能摘要**: 当历史过长时，自动生成摘要
3. **用户认证**: 为每个用户分配独立的 session_id
4. **多模型支持**: 尝试不同的 AI 模型进行对比

## 📝 相关文件

- **实现代码**: 
  - `web_client/app.py` (第 51-721 行)
  - `mcp_ical/deepseek_client.py` (第 92-170 行)
  - `web_client/static/js/app.js` (第 264-285 行)

- **文档**: 
  - `CONTEXT_MEMORY.md` - 完整技术文档
  - 本文件 (`TEST_REPORT.md`) - 测试报告

- **测试脚本**: 
  - `test_context_memory.py` - 自动化测试脚本（可选）

---

**报告生成时间**: 2025-11-11  
**状态**: ✅ 代码实现完成，待手动测试验证
