# 🚀 快速启动指南

本文档提供 iCalendar 智能日历系统的快速安装和启动步骤。

完整文档请查看 [README.md](README.md) | 架构文档请查看 [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)

---

## ⚡ 5分钟快速开始

### 1. 安装 uv 包管理工具

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 克隆并进入项目

```bash
git clone https://github.com/yourusername/iCalendar.git
cd iCalendar
```

### 3. 安装依赖

```bash
uv sync
```

### 4. 配置凭据

#### 4.1 复制配置文件
```bash
cp config.json.example config_private.json
```

#### 4.2 获取 iCloud 应用专用密码

1. 访问 https://appleid.apple.com/
2. 进入"登录与安全" → "应用专用密码"
3. 生成新密码并复制（格式：`xxxx-xxxx-xxxx-xxxx`）

#### 4.3 获取 DeepSeek API 密钥

1. 访问 https://platform.deepseek.com/
2. 创建 API 密钥并复制（格式：`sk-xxxxxxxxxxxxxx`）

#### 4.4 编辑配置文件

```bash
nano config_private.json
# 或使用您喜欢的编辑器
```

填入凭据：

```json
{
  "caldav": {
    "server_url": "https://caldav.icloud.com/",
    "username": "your_apple_id@icloud.com",
    "password": "xxxx-xxxx-xxxx-xxxx"
  },
  "deepseek": {
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com"
  }
}
```

### 5. 启动服务器

#### 前台运行（开发调试）

```bash
uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 --reload
```

#### 后台运行（生产环境）

```bash
nohup uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 > web_server.log 2>&1 &
```

### 6. 访问 Web 界面

打开浏览器访问：**http://localhost:8000**

🎉 完成！

---

## 🛠️ 服务管理

### 启动服务

```bash
# 后台运行
nohup uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 > web_server.log 2>&1 &

# 前台运行（支持热重载）
uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 --reload
```

### 停止服务

```bash
# 按进程名停止
pkill -f "uvicorn web_client.app"

# 或强制停止占用 8000 端口的进程
lsof -ti :8000 | xargs kill -9
```

### 检查服务状态

```bash
# 查看进程
lsof -i :8000

# 测试健康检查
curl http://localhost:8000/api/health

# 查看服务器日志（后台运行时）
tail -f web_server.log
```

### 重启服务

```bash
pkill -f "uvicorn web_client.app" && sleep 2 && \
nohup uv run uvicorn web_client.app:app --host 0.0.0.0 --port 8000 > web_server.log 2>&1 &
```

---

## 💡 使用示例

### 自然语言命令

在智能助手输入框中尝试：

```
# 创建事件
"明天下午3点和张三开会"
"下周三上午9点到10点团队会议"

# 查询事件
"今天有什么安排？"
"本周有什么会议？"

# 更新事件
"把明天的会议改到后天"
"把和张三的会议改到下午2点"

# 删除事件
"删除明天的会议"
"删除和张三的会议"
```

---

## 🔧 常见问题

### 问题 1：无法连接到 iCloud

**解决方案**：
- 确认使用**应用专用密码**（不是 Apple ID 密码）
- 检查网络连接
- 重新生成应用专用密码

### 问题 2：端口被占用

**错误**：`[Errno 48] Address already in use`

**解决方案**：
```bash
lsof -ti :8000 | xargs kill -9
```

### 问题 3：DeepSeek API 失败

**解决方案**：
- 检查 API 密钥是否正确
- 确认 API 配额充足
- 访问 DeepSeek 控制台查看状态

### 问题 4：无法创建事件

**原因**：尝试在只读日历中创建事件

**解决方案**：
- 在 Web 界面选择可写的日历
- 避免在"节假日"等订阅日历中创建

---

## 📊 测试系统

### 健康检查

```bash
curl http://localhost:8000/api/health
```

**期望输出**：
```json
{
  "status": "healthy",
  "calendar_manager": true,
  "deepseek_client": true
}
```

### 获取日历列表

```bash
curl http://localhost:8000/api/calendars
```

### 查询事件

```bash
curl 'http://localhost:8000/api/events?start_date=2025-11-01&end_date=2025-11-30'
```

### 测试自然语言

```bash
curl -X POST http://localhost:8000/api/nl/execute \
  -H "Content-Type: application/json" \
  -d '{"text": "明天下午3点和张三开会"}'
```

---

## 📚 更多资源

- **完整文档**：[README.md](README.md)
- **架构文档**：[PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- **API 文档**：http://localhost:8000/docs（启动服务器后访问）

---

## 🎯 下一步

1. ✅ 在 Web 界面中尝试创建事件
2. ✅ 使用自然语言输入命令
3. ✅ 拖拽调整事件时间
4. ✅ 探索不同的日历视图（月/周/日/列表）
5. ✅ 查看 API 文档了解更多功能

---

<div align="center">

**祝使用愉快！** 🎉

如有问题，请查看 [README.md](README.md) 或提交 [Issue](https://github.com/yourusername/iCalendar/issues)

</div>
