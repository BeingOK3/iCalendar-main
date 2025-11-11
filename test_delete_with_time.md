# 测试：删除带时间的事件

## 修改内容

### 1. 系统提示词增强 (`mcp_ical/deepseek_client.py`)

强化了删除事件时必须提取时间信息的要求：

```
⚠️ 重要：当用户提到"明天"、"今天"、"后天"等时间词时，必须转换为 start_date 或 start_time！
```

示例：
- "明天不打游戏了" → `{"action": "delete_event", "params": {"title": "打游戏", "start_date": "2025-11-12"}}`
- "下午3点的开会取消" → `{"action": "delete_event", "params": {"title": "开会", "start_time": "2025-11-11T15:00:00"}}`

### 2. 删除逻辑增强 (`web_client/app.py` 第608-690行)

添加了基于时间范围的事件搜索：

```python
if target_time_str:
    # 如果指定了具体时间，解析它
    target_datetime = datetime.fromisoformat(target_time_str)
    # 搜索目标时间当天的事件
    start_date = target_datetime.replace(hour=0, minute=0, second=0)
    end_date = start_date + timedelta(days=1)
elif target_date_str:
    # 如果只指定了日期，搜索整天
    target_date = datetime.fromisoformat(target_date_str)
    start_date = target_date.replace(hour=0, minute=0, second=0)
    end_date = start_date + timedelta(days=1)
else:
    # 如果没有指定时间，搜索前后一个月
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now() + timedelta(days=90)
```

### 3. 更新逻辑增强 (`web_client/app.py` 第693-760行)

同样添加了基于 `search_date` 的时间范围过滤。

## 测试场景

### 场景 1：删除明天的特定事件
**输入**: "明天不打游戏了"

**期望行为**:
1. DeepSeek 解析: `{"action": "delete_event", "params": {"title": "打游戏", "start_date": "2025-11-12"}}`
2. 系统搜索 2025-11-12 当天标题包含"打游戏"的事件
3. 只删除明天的"打游戏"，不影响其他日期的同名事件

### 场景 2：删除今天下午的会议
**输入**: "下午3点的会议取消"

**期望行为**:
1. DeepSeek 解析: `{"action": "delete_event", "params": {"title": "会议", "start_time": "2025-11-11T15:00:00"}}`
2. 系统搜索今天下午3点附近的会议
3. 精确删除指定时间的会议

### 场景 3：多个同名事件
**输入**: "明天不打游戏了"（假设明天有2个"打游戏"事件）

**期望行为**:
1. 系统找到2个匹配事件
2. 返回事件列表让用户选择
3. 用户明确指定后再删除

## 优势

✅ **精确匹配**: 通过时间范围过滤，避免误删其他日期的同名事件  
✅ **智能识别**: DeepSeek 自动提取用户输入中的时间信息  
✅ **用户友好**: 当有多个匹配时，列出选项让用户确认  
✅ **向后兼容**: 如果用户没有指定时间，仍然使用原有的模糊搜索逻辑

## 当前日历数据（从日志中）

```
2025-11-11 (今天):
  - 测试会议 @ 14:00
  - 打游戏 @ 20:00
  - 吃饭 @ 20:00

2025-11-12 (明天):
  - 开会 @ 16:00
  - 打游戏 @ 16:00
  - 与bok吃饭 @ 17:00
  - 与bo k @ 17:00

2025-11-15:
  - 打游戏 @ 20:00
```

测试"明天不打游戏了"应该只删除 2025-11-12 @ 16:00 的"打游戏"，不影响其他日期的"打游戏"事件。
