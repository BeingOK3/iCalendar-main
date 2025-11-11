"""mcp_ical.deepseek_client
---------------------------

DeepSeek API 集成模块：提供自然语言处理功能，将用户的自然语言输入转换为结构化的日历操作。

主要功能：
- 解析自然语言日历操作（创建、查询、更新、删除事件）
- 提取日期、时间、事件详情等信息
- 生成结构化的 API 调用参数

使用示例：
>>> client = DeepSeekClient()
>>> result = await client.parse_calendar_command("下周三下午3点提醒我开会")
>>> print(result)
{
    "action": "create_event",
    "params": {
        "title": "开会",
        "start_time": "2025-11-13T15:00:00",
        ...
    }
}
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import httpx
from loguru import logger

from .config import get_config

logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)


class DeepSeekClient:
    """DeepSeek API 客户端，用于自然语言处理"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """初始化 DeepSeek 客户端
        
        Args:
            api_key: DeepSeek API 密钥，如果不提供则从配置文件读取
            base_url: API 基础 URL，默认为 DeepSeek API 地址
        """
        config = get_config()
        
        # 从配置中读取 DeepSeek 设置
        if api_key:
            self.api_key = api_key
        elif config.deepseek and config.deepseek.api_key:
            self.api_key = config.deepseek.api_key
        else:
            self.api_key = None
        
        if base_url:
            self.base_url = base_url
        elif config.deepseek and config.deepseek.base_url:
            self.base_url = config.deepseek.base_url
        else:
            self.base_url = "https://api.deepseek.com"
        
        if not self.api_key:
            raise ValueError(
                "DeepSeek API key not found. Please add it to config_private.json:\n"
                '{\n'
                '  "deepseek": {\n'
                '    "api_key": "your_deepseek_api_key",\n'
                '    "base_url": "https://api.deepseek.com"\n'
                '  }\n'
                '}'
            )
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        logger.info("DeepSeek client initialized successfully")

    async def parse_calendar_command(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """解析用户的自然语言日历命令
        
        Args:
            user_input: 用户的自然语言输入
            context: 可选的上下文信息（如当前日期、用户时区等）
            
        Returns:
            Dict 包含解析后的操作类型和参数：
            {
                "action": "create_event|list_events|update_event|delete_event|query",
                "params": {...},
                "confidence": 0.95,
                "explanation": "解析说明"
            }
        """
        logger.info(f"Parsing calendar command: {user_input}")
        
        # 构建上下文信息
        if context is None:
            context = {}
        
        current_time = context.get("current_time", datetime.now())
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(current_time)
        
        # 构建用户提示词
        user_prompt = self._build_user_prompt(user_input, current_time, context)
        
        # ========== 构建消息列表（支持对话历史）==========
        messages = [{"role": "system", "content": system_prompt}]
        
        # 如果上下文中包含对话历史，添加到消息列表中
        conversation_history = context.get("conversation_history", [])
        if conversation_history:
            # 添加历史对话（不包括系统消息）
            messages.extend(conversation_history)
            logger.info(f"Added {len(conversation_history)} historical messages to API call")
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            # 调用 DeepSeek API
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": messages,  # 使用包含历史的消息列表
                    "temperature": 0.1,  # 使用较低的温度以获得更一致的结果
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"}
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 提取并解析响应
            content = result["choices"][0]["message"]["content"]
            parsed_result = json.loads(content)
            
            logger.info(f"Successfully parsed command: {parsed_result.get('action')}")
            return parsed_result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"DeepSeek API error: {e.response.status_code} - {e.response.text}")
            return {
                "action": "error",
                "error": f"API 调用失败: {e.response.status_code}",
                "explanation": "无法连接到 DeepSeek API"
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse DeepSeek response: {e}")
            return {
                "action": "error",
                "error": "响应解析失败",
                "explanation": "DeepSeek 返回的数据格式不正确"
            }
        except Exception as e:
            logger.error(f"Unexpected error in parse_calendar_command: {e}")
            return {
                "action": "error",
                "error": str(e),
                "explanation": "处理请求时发生未知错误"
            }

    def _build_system_prompt(self, current_time: datetime) -> str:
        """构建系统提示词"""
        return f"""你是一个专业的日历助手，负责理解用户的自然语言输入并将其转换为结构化的日历操作。

当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
当前星期: {self._get_weekday_chinese(current_time.weekday())}

你需要识别以下操作类型：
1. create_event - 创建新事件
2. list_events - 查询事件列表
3. update_event - 更新现有事件
4. delete_event - 删除事件
5. query - 一般性查询

请严格按照以下 JSON 格式返回结果：
{{
    "action": "操作类型",
    "params": {{
        "title": "事件标题（用于 create_event、update_event 和 delete_event）",
        "search_title": "搜索的原标题（仅用于 update_event，如'把明天的会议'中的'明天的会议'）",
        "start_time": "开始时间 ISO8601 格式（如 2025-11-13T15:00:00）",
        "end_time": "结束时间 ISO8601 格式（可选）",
        "location": "地点（可选）",
        "description": "描述（可选）",
        "calendar_name": "日历名称（可选）",
        "event_id": "事件ID（仅当用户明确提供时使用）",
        "start_date": "查询/匹配开始日期（用于 list_events、delete_event、update_event）",
        "end_date": "查询结束日期（仅用于 list_events）",
        "search_date": "搜索事件的日期（仅用于 update_event 按日期查找原事件）"
    }},
    "confidence": 0.95,
    "explanation": "对用户输入的理解说明"
}}

时间解析规则：
- "今天" = {current_time.strftime('%Y-%m-%d')}
- "明天" = {(current_time + timedelta(days=1)).strftime('%Y-%m-%d')}
- "后天" = {(current_time + timedelta(days=2)).strftime('%Y-%m-%d')}
- "下周一" = 下周的周一日期
- "上午9点" = 09:00:00
- "下午3点" = 15:00:00
- "晚上8点" = 20:00:00
- 如果没有指定具体时间，默认使用 09:00:00

注意事项：
1. 所有日期时间必须使用 ISO8601 格式
2. 时区默认使用当地时区（不要添加 +08:00 等后缀）
3. 如果用户没有指定结束时间，默认为开始时间后1小时
4. 置信度应该在 0-1 之间，表示对解析结果的确信程度

删除和更新事件的特殊处理：
- 对于删除操作（如"删除和张三的会议"、"明天不打游戏了"），必须同时提取：
  1. 标题关键词 → title 参数
  2. 时间信息 → start_date（如果只有日期）或 start_time（如果有具体时间）
  
  示例：
  - "删除和张三的会议" → {{"action": "delete_event", "params": {{"title": "张三"}}}}
  - "明天不打游戏了" → {{"action": "delete_event", "params": {{"title": "打游戏", "start_date": "2025-11-12"}}}}
  - "下午3点的开会取消" → {{"action": "delete_event", "params": {{"title": "开会", "start_time": "2025-11-11T15:00:00"}}}}
  
  ⚠️ 重要：当用户提到"明天"、"今天"、"后天"等时间词时，必须转换为 start_date 或 start_time！
  
- 对于更新操作（如"把明天的会议改到后天"），提取原标题到 search_title，原时间到 search_date，新信息到相应字段
  示例1：{{"action": "update_event", "params": {{"search_title": "会议", "search_date": "2025-11-12", "start_time": "2025-11-13T09:00:00"}}}}
  示例2：{{"action": "update_event", "params": {{"search_title": "开会", "start_time": "2025-11-13T15:00:00"}}}}
  
- 系统会自动根据标题和时间范围搜索并匹配事件，无需提供 event_id
- 务必记住：用户提到时间信息时（如"明天"、"下午3点"），必须在 params 中包含对应的日期/时间字段！
"""

    def _build_user_prompt(self, user_input: str, current_time: datetime, context: Dict[str, Any]) -> str:
        """构建用户提示词"""
        prompt = f"请解析以下日历命令：\n\n用户输入: {user_input}\n\n"
        
        # 添加上下文信息
        if context.get("recent_events"):
            prompt += f"最近的事件: {context['recent_events']}\n"
        
        if context.get("calendars"):
            prompt += f"可用的日历: {', '.join(context['calendars'])}\n"
        
        return prompt

    @staticmethod
    def _get_weekday_chinese(weekday: int) -> str:
        """获取中文星期表示"""
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return weekdays[weekday]

    async def generate_event_summary(self, events: list) -> str:
        """生成事件摘要，使用自然语言描述事件列表
        
        Args:
            events: 事件列表
            
        Returns:
            str: 自然语言摘要
        """
        if not events:
            return "没有找到任何事件。"
        
        # 构建事件列表的文本描述
        events_text = "\n".join([
            f"- {e.get('title', '无标题')} ({e.get('start_time')} 到 {e.get('end_time')})"
            for e in events[:10]  # 限制最多10个事件
        ])
        
        system_prompt = "你是一个友好的日历助手，负责用自然、简洁的语言总结用户的日历事件。"
        user_prompt = f"请用简洁的中文总结以下事件列表：\n\n{events_text}\n\n总共有 {len(events)} 个事件。"
        
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
            
            response.raise_for_status()
            result = response.json()
            summary = result["choices"][0]["message"]["content"]
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return f"找到了 {len(events)} 个事件。"

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        logger.info("DeepSeek client closed")

    async def __aenter__(self):
        """支持异步上下文管理器"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持异步上下文管理器"""
        await self.close()
