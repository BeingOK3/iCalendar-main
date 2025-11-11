# iCalendar 智能日历系统 - 项目架构文档

## 📋 项目概述

这是一个基于 Python 的智能日历管理系统，集成了 CalDAV 协议（支持 iCloud）和 DeepSeek AI 自然语言处理能力。用户可以通过 Web 界面或 MCP（Model Context Protocol）服务器以自然语言方式管理日历事件。

**核心功能**：
- 🗓️ CalDAV 日历集成（完全支持 iCloud）
- 🤖 DeepSeek AI 自然语言处理
- 🌐 现代化 Web 界面（FullCalendar）
- 🔌 MCP 服务器支持
- 🔍 智能事件匹配和管理

---

## 📁 项目结构

```
iCalendar-main/
├── mcp_ical/                          # 核心业务逻辑包
│   ├── __init__.py                    # 包初始化文件
│   ├── caldav_client.py               # CalDAV 协议客户端
│   ├── config.py                      # 配置管理模块
│   ├── deepseek_client.py             # DeepSeek AI 客户端
│   ├── ical.py                        # 日历管理器主类
│   ├── models.py                      # 数据模型定义
│   └── server.py                      # MCP 服务器实现
│
├── web_client/                        # Web 应用模块
│   ├── __init__.py                    # Web 包初始化
│   ├── app.py                         # FastAPI 主应用
│   ├── templates/                     # HTML 模板目录
│   │   └── index.html                 # 主页面模板
│   └── static/                        # 静态资源目录
│       ├── css/
│       │   └── style.css              # 全局样式表
│       └── js/
│           └── app.js                 # 前端 JavaScript 逻辑
│
├── config_private.json                # 私有配置文件（不提交到 Git）
├── config.json.example                # 配置文件模板
├── pyproject.toml                     # 项目依赖和元数据
├── uv.lock                            # 依赖锁定文件
├── test_calendar_manager_integration.py  # 集成测试
├── web_server.log                     # Web 服务器日志
├── .gitignore                         # Git 忽略配置
├── LICENSE                            # 开源协议
└── README.md                          # 项目说明文档
```

---

## 🔍 文件详解

### 核心业务逻辑模块 (`mcp_ical/`)

#### 1. `caldav_client.py` - CalDAV 协议客户端
**功能**：实现 CalDAV 协议通信，管理与 iCloud 等日历服务器的交互

**主要类**：
- `CalDAVClient`: CalDAV 客户端主类

**核心方法**：
```python
_connect()              # 连接到 CalDAV 服务器
list_calendars()        # 获取所有日历列表
create_event()          # 创建新事件
update_event()          # 更新现有事件
delete_event()          # 删除事件
list_events()           # 查询指定时间范围的事件
```

**特性**：
- ✅ 自动处理 iCloud CalDAV URL
- ✅ 智能选择可写日历
- ✅ 友好的错误提示（权限、认证等）
- ✅ 支持事件的完整 CRUD 操作

---

#### 2. `config.py` - 配置管理
**功能**：加载和管理应用配置

**数据类**：
```python
@dataclass
class CalDAVConfig:
    server_url: str      # CalDAV 服务器地址
    username: str        # 用户名（Apple ID）
    password: str        # 应用专用密码

@dataclass
class DeepSeekConfig:
    api_key: str         # DeepSeek API 密钥
    base_url: str        # API 基础 URL

@dataclass
class AppConfig:
    caldav: CalDAVConfig
    deepseek: DeepSeekConfig
```

**函数**：
```python
load_config(config_path: str) -> AppConfig
```

**特性**：
- ✅ 支持从 JSON 文件加载配置
- ✅ 类型安全的配置对象
- ✅ 提供 `get()` 方法兼容字典访问

---

#### 3. `deepseek_client.py` - DeepSeek AI 客户端
**功能**：集成 DeepSeek API，实现自然语言理解和处理

**主要类**：
- `DeepSeekClient`: AI 客户端主类

**核心方法**：
```python
parse_calendar_command(user_input, context)
    # 解析自然语言命令为结构化操作
    # 输入: "明天下午3点和张三开会"
    # 输出: {"action": "create_event", "params": {...}}

generate_event_summary(events)
    # 生成事件列表的自然语言摘要
    # 输入: [event1, event2, ...]
    # 输出: "您本周有2个安排：明天上午10点..."
```

**支持的操作类型**：
1. `create_event` - 创建事件
2. `list_events` - 查询事件
3. `update_event` - 更新事件
4. `delete_event` - 删除事件
5. `query` - 一般性查询

**智能特性**：
- ✅ 时间智能解析（今天、明天、下周一等）
- ✅ 自动提取事件标题、时间、地点
- ✅ 支持按标题模糊匹配事件
- ✅ 返回置信度和解析说明

---

#### 4. `ical.py` - 日历管理器主类
**功能**：统一的日历管理接口，整合 CalDAV 客户端功能

**主要类**：
- `CalendarManager`: 日历管理器

**核心方法**：
```python
list_calendars()            # 列出所有日历
list_calendar_names()       # 获取日历名称列表
create_event(request)       # 创建事件（使用请求对象）
update_event(id, request)   # 更新事件
delete_event(id)            # 删除事件
list_events(start, end, calendar_name)  # 查询事件
```

**特性**：
- ✅ 统一的错误处理
- ✅ 详细的日志记录
- ✅ 支持按日历名称筛选

---

#### 5. `models.py` - 数据模型定义
**功能**：定义所有数据模型和请求/响应对象

**数据类**：

```python
@dataclass
class Event:
    """日历事件模型"""
    identifier: str           # 事件唯一标识
    title: str                # 事件标题
    start_time: datetime      # 开始时间
    end_time: datetime | None # 结束时间
    location: str | None      # 地点
    notes: str | None         # 备注
    calendar_name: str | None # 所属日历名称
    
    @property
    def id(self) -> str:
        """提供 id 属性作为 identifier 的别名"""
    
    @property
    def description(self) -> str | None:
        """提供 description 属性作为 notes 的别名"""
    
    @staticmethod
    def _extract_event_id(caldav_event) -> str:
        """从 CalDAV 事件中提取字符串形式的 ID"""
    
    @classmethod
    def from_caldav_event(cls, caldav_event, calendar_name) -> 'Event':
        """从 CalDAV 事件对象创建 Event 实例"""

@dataclass
class CreateEventRequest:
    """创建事件请求"""
    title: str
    start_time: datetime
    end_time: datetime | None = None
    location: str | None = None
    description: str | None = None
    calendar_name: str | None = None

@dataclass
class UpdateEventRequest:
    """更新事件请求"""
    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    location: str | None = None
    description: str | None = None

@dataclass
class NaturalLanguageRequest:
    """自然语言请求"""
    text: str                    # 用户输入文本
    context: dict | None = None  # 上下文信息
```

**特性**：
- ✅ 类型安全
- ✅ 提供属性别名（id/description）
- ✅ 支持从 CalDAV 对象转换
- ✅ 智能 ID 提取（处理复杂对象）

---

#### 6. `server.py` - MCP 服务器实现
**功能**：实现 Model Context Protocol (MCP) 服务器，供 AI 助手调用

**核心功能**：
- 提供 MCP 工具接口
- 支持通过 MCP 协议管理日历
- 可被 Claude、ChatGPT 等 AI 助手调用

**主要方法**：
```python
main()  # 启动 MCP 服务器
```

**使用方式**：
```bash
uv run mcp-ical
```

---

### Web 应用模块 (`web_client/`)

#### 1. `app.py` - FastAPI 主应用
**功能**：实现 RESTful API 和 Web 服务器

**应用实例**：
```python
app = FastAPI(title="iCalendar 智能日历系统")
```

**API 端点**：

##### 健康检查
```
GET /api/health
返回: {"status": "healthy", "calendar_manager": true, "deepseek_client": true}
```

##### 日历管理
```
GET /api/calendars
返回: {"calendars": ["个人", "工作", ...]}
```

##### 事件 CRUD
```
GET    /api/events?start_date=...&end_date=...&calendar_name=...
POST   /api/events
PUT    /api/events/{event_id}
DELETE /api/events/{event_id}
```

##### 自然语言处理
```
POST /api/nl/execute
请求: {"text": "明天下午3点和张三开会"}
返回: {"success": true, "action": "create_event", "message": "已创建事件: ..."}
```

**智能特性**：
- ✅ 支持按标题模糊匹配删除/更新事件
- ✅ 多个匹配时返回列表供用户选择
- ✅ 自动查询最近90天事件进行匹配
- ✅ 完整的错误处理和日志记录

**生命周期管理**：
```python
@app.on_event("startup")
async def startup_event():
    # 初始化 CalendarManager 和 DeepSeekClient

@app.on_event("shutdown")
async def shutdown_event():
    # 清理资源
```

---

#### 2. `templates/index.html` - 主页面模板
**功能**：Web 界面主页，提供可视化日历和交互功能

**技术栈**：
- HTML5 / CSS3
- JavaScript (ES6+)
- FullCalendar 6.1.10
- Font Awesome 图标

**主要功能区**：

1. **侧边栏**
   - 智能助手输入框（自然语言）
   - 快捷操作按钮（创建事件、今天、刷新）
   - 日历筛选器
   - 系统状态显示

2. **主日历区域**
   - 月/周/日/列表视图切换
   - 拖拽创建事件
   - 拖拽调整事件时间
   - 点击事件查看/编辑详情

3. **事件模态框**
   - 创建新事件表单
   - 编辑现有事件
   - 删除确认

**特性**：
- ✅ 响应式设计（适配手机/平板）
- ✅ 实时同步日历数据
- ✅ 平滑动画效果
- ✅ 快捷键支持

---

#### 3. `static/css/style.css` - 全局样式表
**功能**：定义 Web 界面的所有样式

**样式组织**：
```css
/* 全局变量 */
:root {
    --primary-color: #4a90e2;
    --success-color: #4caf50;
    --danger-color: #f44336;
    /* ... */
}

/* 布局 */
.app-container { /* 主容器 */ }
.sidebar { /* 侧边栏 */ }
.main-content { /* 主内容区 */ }

/* 组件 */
.smart-assistant { /* 智能助手 */ }
.quick-actions { /* 快捷操作 */ }
.calendar-filter { /* 日历筛选 */ }
.event-modal { /* 事件模态框 */ }

/* 响应式 */
@media (max-width: 768px) { /* 移动设备 */ }
```

**特性**：
- ✅ CSS Grid / Flexbox 布局
- ✅ CSS 变量管理颜色主题
- ✅ 平滑过渡动画
- ✅ 移动优先设计
- ✅ 暗色主题友好

---

#### 4. `static/js/app.js` - 前端逻辑
**功能**：实现前端交互和 API 通信

**核心函数**：

```javascript
// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    initCalendar();      // 初始化 FullCalendar
    loadCalendars();     // 加载日历列表
    loadEvents();        // 加载事件
    setupEventListeners(); // 设置事件监听
});

// API 调用
async function loadEvents() { /* 加载事件 */ }
async function createEvent(eventData) { /* 创建事件 */ }
async function updateEvent(eventId, updates) { /* 更新事件 */ }
async function deleteEvent(eventId) { /* 删除事件 */ }
async function processNaturalLanguage(text) { /* 自然语言处理 */ }

// UI 交互
function showEventModal(event) { /* 显示事件详情 */ }
function showMessage(message, type) { /* 显示提示消息 */ }
function updateSystemStatus(status) { /* 更新系统状态 */ }
```

**FullCalendar 配置**：
```javascript
const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    headerToolbar: { /* 工具栏配置 */ },
    editable: true,          // 可编辑
    droppable: true,         // 可拖放
    selectable: true,        // 可选择
    events: loadEvents,      // 事件源
    eventDrop: handleEventDrop,      // 拖动事件
    eventResize: handleEventResize,  // 调整大小
    dateClick: handleDateClick,      // 日期点击
    eventClick: handleEventClick     // 事件点击
});
```

**特性**：
- ✅ 异步 API 调用（async/await）
- ✅ 错误处理和用户反馈
- ✅ 防抖处理（避免重复请求）
- ✅ 自动刷新事件列表

---

### 配置文件

#### 1. `config.json.example` - 配置模板
**功能**：提供配置文件示例

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

#### 2. `config_private.json` - 实际配置
**功能**：存储真实的凭据（已添加到 .gitignore）

**安全提示**：
- ⚠️ 不要提交到 Git
- ⚠️ 使用 iCloud 应用专用密码，不是 Apple ID 密码
- ⚠️ 定期更换 API 密钥

---

#### 3. `pyproject.toml` - 项目配置
**功能**：定义项目元数据和依赖

```toml
[project]
name = "mcp-ical"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "loguru>=0.7.3",        # 日志
    "mcp[cli]>=1.2.1",      # MCP 协议
    "caldav>=1.15",         # CalDAV 客户端
    "requests>=2.31.0",     # HTTP 请求
    "vobject>=0.9.6",       # iCalendar 解析
    "fastapi>=0.111.0",     # Web 框架
    "uvicorn>=0.34.0",      # ASGI 服务器
    "httpx>=0.27.0",        # 异步 HTTP 客户端
    "jinja2>=3.1.0",        # 模板引擎
]

[project.scripts]
mcp-ical = "mcp_ical.server:main"
web-client = "web_client.app:main"
```

---

### 测试文件

#### `test_calendar_manager_integration.py`
**功能**：集成测试套件

**测试用例**：
- 连接 CalDAV 服务器
- 列出日历
- 创建/更新/删除事件
- 查询事件

**运行方式**：
```bash
uv run pytest test_calendar_manager_integration.py -v
```

---

## 🔄 数据流

### 1. 创建事件流程（自然语言）

```
用户输入
  ↓
"明天下午3点和张三开会"
  ↓
前端 (app.js)
  ↓
POST /api/nl/execute
  ↓
FastAPI (app.py)
  ↓
DeepSeekClient.parse_calendar_command()
  ↓
解析结果: {
  "action": "create_event",
  "params": {
    "title": "和张三开会",
    "start_time": "2025-11-12T15:00:00"
  }
}
  ↓
CalendarManager.create_event()
  ↓
CalDAVClient.create_event()
  ↓
iCloud CalDAV 服务器
  ↓
返回事件对象
  ↓
Event.from_caldav_event()
  ↓
返回给前端
  ↓
FullCalendar 刷新显示
```

### 2. 删除事件流程（按标题）

```
用户输入
  ↓
"删除和张三的会议"
  ↓
POST /api/nl/execute
  ↓
DeepSeek 解析: {
  "action": "delete_event",
  "params": {"title": "张三"}
}
  ↓
检查是否有 event_id
  ↓
没有 → 搜索匹配事件
  ↓
CalendarManager.list_events(最近90天)
  ↓
模糊匹配标题包含"张三"的事件
  ↓
找到1个 → 直接删除
找到多个 → 返回列表供选择
找到0个 → 返回"未找到"
  ↓
CalDAVClient.delete_event(event_id)
  ↓
返回成功消息
```

---

## 🎨 技术栈

### 后端
- **Python 3.12+**
- **FastAPI** - 现代 Web 框架
- **Uvicorn** - ASGI 服务器
- **CalDAV** - 日历协议库
- **vobject** - iCalendar 格式处理
- **httpx** - 异步 HTTP 客户端
- **loguru** - 日志库

### 前端
- **HTML5 / CSS3** - 页面结构和样式
- **JavaScript ES6+** - 交互逻辑
- **FullCalendar 6.1.10** - 日历组件
- **Font Awesome** - 图标库

### AI
- **DeepSeek API** - 自然语言理解

### 协议
- **CalDAV** - 日历数据同步
- **MCP (Model Context Protocol)** - AI 助手集成
- **REST API** - Web 服务接口

---

## 🔐 安全性

### 凭据管理
- ✅ 配置文件不提交到 Git (.gitignore)
- ✅ 使用应用专用密码（不是主密码）
- ✅ 环境隔离（虚拟环境）

### API 安全
- ✅ CORS 配置
- ✅ 输入验证
- ✅ 错误信息不泄露敏感数据

---

## 📊 性能特性

### 后端
- ✅ 异步 I/O (FastAPI + httpx)
- ✅ 连接复用
- ✅ 日志级别控制

### 前端
- ✅ 事件按需加载
- ✅ 防抖处理
- ✅ 缓存日历列表
- ✅ 懒加载静态资源

---

## 🧪 测试策略

### 单元测试
- 模型转换测试
- 配置加载测试
- API 端点测试

### 集成测试
- CalDAV 连接测试
- 事件 CRUD 测试
- 自然语言解析测试

### 运行测试
```bash
# 所有测试
uv run pytest

# 详细输出
uv run pytest -v

# 覆盖率报告
uv run pytest --cov=mcp_ical --cov=web_client
```

---

## 🚀 部署建议

### 开发环境
```bash
uv run uvicorn web_client.app:app --reload
```

### 生产环境
```bash
# 使用多 Worker
uvicorn web_client.app:app --workers 4 --host 0.0.0.0 --port 8000

# 使用 systemd 管理服务
# 使用 Nginx 作为反向代理
# 配置 SSL/TLS 证书
```

---

## 📝 日志管理

### 日志位置
- Web 服务器：`web_server.log`
- 应用日志：通过 loguru 输出

### 日志级别
- INFO: 正常操作
- WARNING: 警告信息
- ERROR: 错误详情
- DEBUG: 调试信息（开发模式）

---

## 🔧 维护和扩展

### 添加新功能
1. 在 `models.py` 中定义新的数据模型
2. 在 `caldav_client.py` 或 `ical.py` 中实现业务逻辑
3. 在 `app.py` 中添加 API 端点
4. 在 `app.js` 中添加前端调用
5. 更新 `index.html` 添加 UI 组件

### 更新依赖
```bash
# 更新所有依赖
uv sync --upgrade

# 更新特定包
uv add package_name@latest
```

---

## 📚 相关资源

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [FullCalendar 文档](https://fullcalendar.io/docs)
- [CalDAV 规范](https://tools.ietf.org/html/rfc4791)
- [DeepSeek API 文档](https://platform.deepseek.com/docs)
- [MCP 协议](https://modelcontextprotocol.io/)

---

**文档版本**: 1.0  
**最后更新**: 2025-11-11  
**维护者**: iCalendar Development Team
