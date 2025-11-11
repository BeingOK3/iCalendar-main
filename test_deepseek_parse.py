#!/usr/bin/env python3
"""测试 DeepSeek 解析"明天不打游戏了"的结果"""

import asyncio
import json
from datetime import datetime
from mcp_ical.deepseek_client import DeepSeekClient

async def test_parse():
    client = DeepSeekClient()
    
    context = {
        "current_time": datetime(2025, 11, 11, 19, 30, 0)
    }
    
    result = await client.parse_calendar_command("明天不打游戏了", context)
    
    print("=" * 60)
    print("测试输入: 明天不打游戏了")
    print("当前时间: 2025-11-11 19:30:00")
    print("=" * 60)
    print("\nDeepSeek 解析结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n" + "=" * 60)
    
    # 检查关键字段
    action = result.get("action")
    params = result.get("params", {})
    
    print("\n关键字段检查:")
    print(f"  action: {action}")
    print(f"  title: {params.get('title')}")
    print(f"  start_date: {params.get('start_date')}")
    print(f"  start_time: {params.get('start_time')}")
    
    if action == "delete_event" and params.get("title") == "打游戏":
        if params.get("start_date") == "2025-11-12":
            print("\n✅ 解析正确！包含了标题和日期")
        else:
            print(f"\n❌ 解析错误：start_date 应该是 '2025-11-12'，但得到 '{params.get('start_date')}'")
    else:
        print(f"\n❌ 解析错误：action 或 title 不正确")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_parse())
