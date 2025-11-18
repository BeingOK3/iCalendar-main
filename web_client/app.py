"""web_client.app
-----------------

Web 客户端后端服务：使用 FastAPI 构建 RESTful API，集成 DeepSeek 自然语言处理和现有的日历管理功能。

主要功能：
- 提供 RESTful API 接口用于日历操作
- 集成 DeepSeek API 进行自然语言处理
- 提供静态文件服务（HTML/CSS/JS）
- WebSocket 支持（用于实时通知，可选）

启动方式：
    uvicorn web_client.app:app --host 0.0.0.0 --port 8000 --reload
    或使用命令：uv run web-client
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from mcp_ical.deepseek_client import DeepSeekClient
from mcp_ical.ical import CalendarManager
from mcp_ical.models import CreateEventRequest, UpdateEventRequest, Event

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
)

# 创建 FastAPI 应用
app = FastAPI(
    title="iCalendar Web Client",
    description="一体式日历系统，支持自然语言处理",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取当前文件所在目录
BASE_DIR = Path(__file__).resolve().parent

# 挂载静态文件目录
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 全局变量（生产环境应该使用依赖注入）
calendar_manager: Optional[CalendarManager] = None
deepseek_client: Optional[DeepSeekClient] = None

# ============== 对话历史管理 ==============
# 使用内存存储对话历史，用于实现上下文记忆功能
# 注意：服务器重启后会丢失所有历史记录
from collections import deque
from typing import Deque, Dict

# 每个会话的对话历史记录（最多保存最近 20 条消息）
conversation_history: Dict[str, Deque[dict]] = {}
MAX_HISTORY_LENGTH = 20  # 每个会话最多保存 20 条历史消息

def get_conversation_history(session_id: str = "default") -> Deque[dict]:
    """
    获取指定会话的对话历史
    
    Args:
        session_id: 会话 ID，默认为 "default"（单用户场景）
        
    Returns:
        该会话的对话历史队列
    """
    if session_id not in conversation_history:
        conversation_history[session_id] = deque(maxlen=MAX_HISTORY_LENGTH)
    return conversation_history[session_id]

def add_to_history(session_id: str, role: str, content: str):
    """
    添加一条消息到对话历史
    
    Args:
        session_id: 会话 ID
        role: 角色（"user" 或 "assistant"）
        content: 消息内容
    """
    history = get_conversation_history(session_id)
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })

def clear_history(session_id: str = "default"):
    """
    清空指定会话的对话历史
    
    Args:
        session_id: 会话 ID
    """
    if session_id in conversation_history:
        conversation_history[session_id].clear()
        logger.info(f"Cleared conversation history for session: {session_id}")

def get_history_for_api(session_id: str = "default", max_messages: int = 10) -> List[dict]:
    """
    获取格式化的历史记录用于 API 调用
    
    Args:
        session_id: 会话 ID
        max_messages: 最多返回的消息数量（默认最近 10 条）
        
    Returns:
        格式化的消息列表，适合传递给 DeepSeek API
    """
    history = get_conversation_history(session_id)
    # 只取最近的 N 条消息
    recent = list(history)[-max_messages:] if len(history) > max_messages else list(history)
    # 转换为 API 需要的格式（移除 timestamp）
    return [{"role": msg["role"], "content": msg["content"]} for msg in recent]
# ============================================


# Pydantic 模型定义
class NaturalLanguageRequest(BaseModel):
    """自然语言请求模型"""
    text: str = Field(..., description="用户的自然语言输入")
    session_id: Optional[str] = Field("default", description="会话 ID，用于区分不同用户或会话")
    context: Optional[dict] = Field(None, description="可选的上下文信息")


class CalendarEventResponse(BaseModel):
    """日历事件响应模型"""
    id: str
    title: str
    start_time: str
    end_time: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    calendar_name: Optional[str] = None


class ApiResponse(BaseModel):
    """统一的 API 响应模型"""
    success: bool
    message: str
    data: Optional[dict] = None


# 启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    global calendar_manager, deepseek_client
    
    try:
        # 初始化日历管理器
        calendar_manager = CalendarManager()
        logger.info("Calendar manager initialized successfully")
        
        # 初始化 DeepSeek 客户端
        deepseek_client = DeepSeekClient()
        logger.info("DeepSeek client initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # 不抛出异常，让应用继续运行，但会在使用时提示错误


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    global deepseek_client
    
    if deepseek_client:
        await deepseek_client.close()
        logger.info("DeepSeek client closed")


# ========== 对话历史管理 API ==========
@app.delete("/api/conversation/clear")
async def clear_conversation_history(session_id: str = "default"):
    """
    清空指定会话的对话历史
    
    Args:
        session_id: 会话 ID（默认为 "default"）
        
    Returns:
        成功或失败的响应
    """
    try:
        clear_history(session_id)
        return {
            "success": True,
            "message": "对话历史已清空"
        }
    except Exception as e:
        logger.error(f"Error clearing conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversation/history")
async def get_conversation_history_api(session_id: str = "default"):
    """
    获取指定会话的对话历史
    
    Args:
        session_id: 会话 ID（默认为 "default"）
        
    Returns:
        对话历史列表
    """
    try:
        history = list(get_conversation_history(session_id))
        return {
            "success": True,
            "session_id": session_id,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 路由定义
@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页"""
    index_file = templates_dir / "index.html"
    
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    else:
        return """
        <html>
            <head><title>iCalendar Web Client</title></head>
            <body>
                <h1>欢迎使用 iCalendar Web Client</h1>
                <p>前端模板文件未找到，请检查 web_client/templates/index.html</p>
                <p>API 文档: <a href="/docs">/docs</a></p>
            </body>
        </html>
        """


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "calendar_manager": calendar_manager is not None,
        "deepseek_client": deepseek_client is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/calendars", response_model=List[str])
async def list_calendars():
    """获取所有可用的日历列表"""
    if not calendar_manager:
        raise HTTPException(status_code=503, detail="Calendar manager not initialized")
    
    try:
        calendars = calendar_manager.list_calendar_names()
        return calendars
    except Exception as e:
        logger.error(f"Error listing calendars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def list_events(
    start_date: Optional[str] = Query(None, description="开始日期 (ISO8601)"),
    end_date: Optional[str] = Query(None, description="结束日期 (ISO8601)"),
    calendar_name: Optional[str] = Query(None, description="日历名称")
):
    """获取事件列表"""
    if not calendar_manager:
        raise HTTPException(status_code=503, detail="Calendar manager not initialized")
    
    try:
        # 解析日期，如果未提供则使用默认值（今天到未来30天）
        if start_date:
            start = datetime.fromisoformat(start_date)
        else:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if end_date:
            end = datetime.fromisoformat(end_date)
        else:
            end = start + timedelta(days=30)
        
        events = calendar_manager.list_events(start, end, calendar_name)
        
        # ========== 调试日志：显示日历视图查询的事件 ==========
        logger.info(f"📊 Calendar view query found {len(events)} events from {start} to {end}")
        for evt in events[:10]:  # 只显示前10个
            logger.info(f"  📌 {evt.title} | Start: {evt.start_time}")
        
        # 转换为字典格式
        events_data = []
        for event in events:
            events_data.append({
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "location": event.location,
                "description": event.description,
                "calendar_name": getattr(event, 'calendar_name', None)
            })
        
        return {
            "success": True,
            "count": len(events_data),
            "events": events_data
        }
        
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/events")
async def create_event(event_request: CreateEventRequest):
    """创建新事件"""
    if not calendar_manager:
        raise HTTPException(status_code=503, detail="Calendar manager not initialized")
    
    try:
        event = calendar_manager.create_event(event_request)
        
        return {
            "success": True,
            "message": "事件创建成功",
            "data": {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/events/{event_id:path}")
async def update_event(event_id: str, update_request: UpdateEventRequest):
    """更新事件 - 支持包含斜杠的事件ID"""
    if not calendar_manager:
        raise HTTPException(status_code=503, detail="Calendar manager not initialized")
    
    try:
        event = calendar_manager.update_event(event_id, update_request)
        
        return {
            "success": True,
            "message": "事件更新成功",
            "data": {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/events/{event_id:path}")
async def delete_event(event_id: str):
    """删除事件 - 支持包含斜杠的事件ID"""
    if not calendar_manager:
        raise HTTPException(status_code=503, detail="Calendar manager not initialized")
    
    try:
        # URL 解码事件 ID（FastAPI 会自动解码）
        success = calendar_manager.delete_event(event_id)
        
        if success:
            return {
                "success": True,
                "message": "事件删除成功"
            }
        else:
            raise HTTPException(status_code=404, detail="Event not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/nl/parse")
async def parse_natural_language(request: NaturalLanguageRequest):
    """解析自然语言命令"""
    if not deepseek_client:
        raise HTTPException(status_code=503, detail="DeepSeek client not initialized")
    
    try:
        # 添加当前可用的日历到上下文
        context = request.context or {}
        if calendar_manager and "calendars" not in context:
            context["calendars"] = calendar_manager.list_calendar_names()
        
        # 解析命令
        result = await deepseek_client.parse_calendar_command(request.text, context)
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error parsing natural language: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/nl/execute")
async def execute_natural_language(request: NaturalLanguageRequest):
    """
    解析并执行自然语言命令（一步完成）
    
    支持上下文记忆：
    - 自动保存每次对话到会话历史
    - 将最近的对话历史传递给 AI，使其能理解上下文
    - 使用 session_id 区分不同会话（默认为 "default"）
    """
    if not deepseek_client or not calendar_manager:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        session_id = request.session_id or "default"
        
        # ========== 获取对话历史（在添加当前消息之前）==========
        # 获取最近 5 轮对话（10 条消息）用于上下文理解
        # 注意：此时不包含当前用户消息，当前消息会在 DeepSeek 客户端中添加
        history_messages = get_history_for_api(session_id, max_messages=10)
        
        # 添加上下文
        context = request.context or {}
        if "calendars" not in context:
            context["calendars"] = calendar_manager.list_calendar_names()
        
        # ========== 将历史对话添加到上下文中 ==========
        # DeepSeek API 可以利用这些历史对话来理解用户的意图
        if history_messages:
            context["conversation_history"] = history_messages
            logger.info(f"Using {len(history_messages)} historical messages for context")
        
        # ========== 解析命令（当前用户输入会在这里发送给 API）==========
        parsed = await deepseek_client.parse_calendar_command(request.text, context)
        
        # ========== 调试日志：显示解析结果 ==========
        logger.info(f"🤖 DeepSeek parsed result: action={parsed.get('action')}, params={parsed.get('params')}")
        
        # ========== 解析成功后，保存当前用户消息到历史 ==========
        add_to_history(session_id, "user", request.text)
        
        if parsed.get("action") == "error":
            return {
                "success": False,
                "message": parsed.get("explanation", "解析失败"),
                "error": parsed.get("error")
            }
        
        # 根据解析结果执行相应操作
        action = parsed.get("action")
        params = parsed.get("params", {})
        
        if action == "batch_create":
            # 批量创建多个事件
            events_data = parsed.get("events", [])
            
            if not events_data:
                return {
                    "success": False,
                    "message": "没有找到要创建的事件"
                }
            
            created_events = []
            failed_events = []
            
            for event_data in events_data:
                try:
                    event_request = CreateEventRequest(
                        title=event_data.get("title", "未命名事件"),
                        start_time=datetime.fromisoformat(event_data["start_time"]),
                        end_time=datetime.fromisoformat(event_data["end_time"]) if event_data.get("end_time") else None,
                        location=event_data.get("location"),
                        description=event_data.get("description"),
                        calendar_name=event_data.get("calendar_name")
                    )
                    event = calendar_manager.create_event(event_request)
                    created_events.append({
                        "id": event.id,
                        "title": event.title,
                        "start_time": event.start_time.isoformat() if event.start_time else None
                    })
                    logger.info(f"✅ Created event: {event.title}")
                except Exception as e:
                    failed_events.append({
                        "title": event_data.get("title", "未命名"),
                        "error": str(e)
                    })
                    logger.error(f"❌ Failed to create event: {event_data.get('title')} - {e}")
            
            # 构建响应消息
            if created_events:
                event_names = [e["title"] for e in created_events]
                response_message = f"已创建 {len(created_events)} 个事件: {', '.join(event_names)}"
                if failed_events:
                    response_message += f"\n失败 {len(failed_events)} 个"
            else:
                response_message = "所有事件创建失败"
            
            # ========== 将助手回复添加到历史 ==========
            add_to_history(session_id, "assistant", response_message)
            
            return {
                "success": len(created_events) > 0,
                "action": "batch_create",
                "message": response_message,
                "data": {
                    "created": created_events,
                    "failed": failed_events,
                    "total": len(events_data),
                    "success_count": len(created_events),
                    "failed_count": len(failed_events)
                }
            }
        
        elif action == "create_event":
            # 创建单个事件
            event_request = CreateEventRequest(
                title=params.get("title", "未命名事件"),
                start_time=datetime.fromisoformat(params["start_time"]),
                end_time=datetime.fromisoformat(params["end_time"]) if params.get("end_time") else None,
                location=params.get("location"),
                description=params.get("description"),
                calendar_name=params.get("calendar_name")
            )
            event = calendar_manager.create_event(event_request)
            
            # ========== 将助手回复添加到历史 ==========
            response_message = f"已创建事件: {event.title}"
            add_to_history(session_id, "assistant", response_message)
            
            return {
                "success": True,
                "action": "create_event",
                "message": response_message,
                "data": {
                    "id": event.id,
                    "title": event.title,
                    "start_time": event.start_time.isoformat() if event.start_time else None
                }
            }
        
        elif action == "list_events":
            # 查询事件
            start = datetime.fromisoformat(params["start_date"])
            end = datetime.fromisoformat(params["end_date"])
            
            # ========== 修复：如果 start 和 end 是同一天，end 应该是第二天 00:00:00 ==========
            # DeepSeek 可能返回 start_date='2025-11-18', end_date='2025-11-18'
            # 这意味着查询"今天"，但转换后 start=end=2025-11-18 00:00:00（范围为0）
            # 我们需要将 end 设置为第二天 00:00:00 以覆盖整天
            if start.date() == end.date() and end.time() == datetime.min.time():
                end = end + timedelta(days=1)
                logger.debug(f"📅 Adjusted end date to next day for full day coverage: {end}")
            
            # ========== 调试日志：记录查询参数 ==========
            logger.info(f"🔍 Querying events: start={start}, end={end}, calendar={params.get('calendar_name')}")
            
            # CalDAV 层已经处理了 iCloud 短时间范围查询的 bug，这里直接调用即可
            events = calendar_manager.list_events(start, end, params.get("calendar_name"))
            
            # ========== 调试日志：记录查询结果 ==========
            logger.info(f"📋 Found {len(events)} events")
            
            # ========== 详细日志：显示每个事件的时间 ==========
            if events:
                for evt in events:
                    logger.info(f"  📌 Event: {evt.title} | Start: {evt.start_time} | End: {evt.end_time}")
            else:
                logger.warning(f"⚠️ No events found in range {start} to {end}")
            
            events_data = [
                {
                    "id": e.id,
                    "title": e.title,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "end_time": e.end_time.isoformat() if e.end_time else None
                }
                for e in events
            ]
            
            # ========== 调试日志：显示事件详情 ==========
            if events_data:
                logger.info(f"📅 Events details: {[e['title'] for e in events_data[:5]]}")
            
            # 生成摘要
            summary = await deepseek_client.generate_event_summary(events_data)
            
            # ========== 将助手回复添加到历史 ==========
            add_to_history(session_id, "assistant", summary)
            
            return {
                "success": True,
                "action": "list_events",
                "message": summary,
                "data": {
                    "count": len(events_data),
                    "events": events_data
                }
            }
        
        elif action == "delete_event":
            # 删除事件
            event_id = params.get("event_id")
            event_title = params.get("title")
            target_date_str = params.get("start_date")  # 目标日期（如"2025-11-12"）
            target_time_str = params.get("start_time")  # 目标时间（如"2025-11-12T14:00:00"）
            
            logger.info(f"🗑️ DELETE EVENT: event_id={event_id}, title={event_title}, start_date={target_date_str}, start_time={target_time_str}")
            
            # 如果没有提供 event_id，尝试通过标题和时间查找
            if not event_id and event_title:
                # 确定目标时间范围（用于过滤）
                target_start = None
                target_end = None
                
                if target_time_str:
                    # 如果指定了具体时间，解析它
                    target_datetime = datetime.fromisoformat(target_time_str)
                    target_start = target_datetime.replace(hour=0, minute=0, second=0)
                    target_end = target_start + timedelta(days=1)
                    logger.info(f"📅 Using target_time_str: {target_time_str}")
                elif target_date_str:
                    # 如果只指定了日期，设置目标范围
                    target_date = datetime.fromisoformat(target_date_str)
                    target_start = target_date.replace(hour=0, minute=0, second=0)
                    target_end = target_start + timedelta(days=1)
                    logger.info(f"📅 Using target_date_str: {target_date_str}, target range: {target_start} - {target_end}")
                
                # ========== 确定查询范围 ==========
                if target_start:
                    # 有目标时间：查询当天
                    query_start = target_start
                    query_end = target_end
                    logger.info(f"📅 Using target date range: {query_start} - {query_end}")
                else:
                    # 没有目标时间：使用默认范围
                    query_start = datetime.now() - timedelta(days=30)
                    query_end = datetime.now() + timedelta(days=90)
                    logger.info(f"📅 No time specified, using default range")
                
                logger.info(f"🔍 Searching for event to delete: title='{event_title}', range={query_start} to {query_end}")
                # CalDAV 层已经处理了短时间范围查询的 bug
                events = calendar_manager.list_events(query_start, query_end)
                logger.info(f"📦 Retrieved {len(events)} events from calendar")
                
                # 打印所有事件用于调试
                for evt in events:
                    logger.info(f"  📌 Event: {evt.title} | Start: {evt.start_time}")
                
                # 查找标题匹配的事件
                if event_title == "*":
                    # 批量删除：匹配所有事件
                    matching_events = events
                    logger.info(f"📋 Batch delete mode: matched all {len(matching_events)} events")
                else:
                    # 单个删除：模糊匹配标题
                    matching_events = [
                        e for e in events 
                        if event_title.lower() in e.title.lower() or e.title.lower() in event_title.lower()
                    ]
                    logger.info(f"📋 Found {len(matching_events)} matching events")
                
                if not matching_events:
                    time_desc = ""
                    if target_date_str or target_time_str:
                        time_desc = f"在指定时间范围内"
                    
                    if event_title == "*":
                        return {
                            "success": True,
                            "message": f"{time_desc}没有找到任何事件"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"{time_desc}没有找到标题包含 '{event_title}' 的事件"
                        }
                
                # 处理批量删除
                if event_title == "*" and len(matching_events) > 1:
                    # 批量删除多个事件
                    deleted_count = 0
                    failed_count = 0
                    deleted_titles = []
                    
                    for event in matching_events:
                        if calendar_manager.delete_event(event.id):
                            deleted_count += 1
                            deleted_titles.append(event.title)
                        else:
                            failed_count += 1
                    
                    logger.info(f"✅ Batch delete completed: {deleted_count} deleted, {failed_count} failed")
                    
                    # 构建响应消息
                    time_desc = ""
                    if target_date_str:
                        date_obj = datetime.fromisoformat(target_date_str)
                        time_desc = date_obj.strftime('%Y年%m月%d日')
                    
                    if deleted_count > 0:
                        response_message = f"已删除{time_desc} {deleted_count} 个事件"
                        if deleted_count <= 5:
                            response_message += f": {', '.join(deleted_titles)}"
                    else:
                        response_message = "删除失败"
                    
                    # ========== 将助手回复添加到历史 ==========
                    add_to_history(session_id, "assistant", response_message)
                    
                    return {
                        "success": deleted_count > 0,
                        "action": "delete_event",
                        "message": response_message,
                        "data": {
                            "deleted_count": deleted_count,
                            "failed_count": failed_count
                        }
                    }
                
                # 处理单个事件删除
                if len(matching_events) > 1:
                    # 找到多个匹配，返回列表让用户选择
                    events_list = [
                        {
                            "id": e.id,
                            "title": e.title,
                            "start_time": e.start_time.isoformat() if e.start_time else None
                        }
                        for e in matching_events
                    ]
                    return {
                        "success": False,
                        "message": f"找到 {len(matching_events)} 个匹配的事件，请明确指定：",
                        "data": {"events": events_list}
                    }
                
                # 只找到一个匹配，使用它
                event_id = matching_events[0].id
                event_title = matching_events[0].title
                logger.info(f"✅ Found unique match: event_id={event_id}, title={event_title}")
            
            if not event_id:
                return {
                    "success": False,
                    "message": "请提供要删除的事件标题或ID"
                }
            
            success = calendar_manager.delete_event(event_id)
            response_message = f"已删除事件: {event_title}" if success else "删除失败"
            
            # ========== 将助手回复添加到历史 ==========
            add_to_history(session_id, "assistant", response_message)
            
            return {
                "success": success,
                "action": "delete_event",
                "message": response_message
            }
        
        elif action == "update_event":
            # 更新事件
            event_id = params.get("event_id")
            search_title = params.get("search_title")  # 用于搜索的原标题
            search_date_str = params.get("search_date")  # 用于搜索的日期
            
            # 如果没有提供 event_id，尝试通过标题和时间查找
            if not event_id and search_title:
                # 确定搜索时间范围
                if search_date_str:
                    # 如果指定了搜索日期，只搜索那一天
                    search_date = datetime.fromisoformat(search_date_str)
                    start_date = search_date.replace(hour=0, minute=0, second=0)
                    end_date = start_date + timedelta(days=1)
                else:
                    # 如果没有指定搜索日期，搜索前后一个月
                    start_date = datetime.now() - timedelta(days=30)
                    end_date = datetime.now() + timedelta(days=90)
                
                logger.info(f"🔍 Searching for event to update: title='{search_title}', range={start_date} to {end_date}")
                # CalDAV 层已经处理了短时间范围查询的 bug
                events = calendar_manager.list_events(start_date, end_date)
                
                # 查找标题匹配的事件（模糊匹配）
                matching_events = [
                    e for e in events 
                    if search_title.lower() in e.title.lower() or e.title.lower() in search_title.lower()
                ]
                
                logger.info(f"📋 Found {len(matching_events)} matching events for update")
                
                if not matching_events:
                    time_desc = ""
                    if search_date_str:
                        time_desc = f"在指定时间范围内"
                    return {
                        "success": False,
                        "message": f"{time_desc}没有找到标题包含 '{search_title}' 的事件"
                    }
                
                if len(matching_events) > 1:
                    # 找到多个匹配，返回列表让用户选择
                    events_list = [
                        {
                            "id": e.id,
                            "title": e.title,
                            "start_time": e.start_time.isoformat() if e.start_time else None
                        }
                        for e in matching_events
                    ]
                    return {
                        "success": False,
                        "message": f"找到 {len(matching_events)} 个匹配的事件，请明确指定：",
                        "data": {"events": events_list}
                    }
                
                # 只找到一个匹配，使用它
                event_id = matching_events[0].id
            
            if not event_id:
                return {
                    "success": False,
                    "message": "请提供要更新的事件标题或ID"
                }
            
            update_fields = {}
            if "title" in params and params["title"] != search_title:
                update_fields["title"] = params["title"]
            if "start_time" in params:
                update_fields["start_time"] = datetime.fromisoformat(params["start_time"])
            if "end_time" in params:
                update_fields["end_time"] = datetime.fromisoformat(params["end_time"])
            if "location" in params:
                update_fields["location"] = params["location"]
            if "description" in params:
                update_fields["description"] = params["description"]
            
            update_request = UpdateEventRequest(**update_fields)
            event = calendar_manager.update_event(event_id, update_request)
            
            response_message = f"已更新事件: {event.title}"
            # ========== 将助手回复添加到历史 ==========
            add_to_history(session_id, "assistant", response_message)
            
            return {
                "success": True,
                "action": "update_event",
                "message": response_message,
                "data": {
                    "id": event.id,
                    "title": event.title
                }
            }
        
        else:
            # 未知操作或一般查询
            response_message = parsed.get("explanation", "已理解您的请求")
            # ========== 将助手回复添加到历史 ==========
            add_to_history(session_id, "assistant", response_message)
            
            return {
                "success": True,
                "action": action,
                "message": response_message,
                "data": parsed
            }
            
    except Exception as e:
        logger.error(f"Error executing natural language command: {e}")
        return {
            "success": False,
            "message": f"执行命令时出错: {str(e)}"
        }


def main():
    """主函数，用于命令行启动"""
    import uvicorn
    
    uvicorn.run(
        "web_client.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
