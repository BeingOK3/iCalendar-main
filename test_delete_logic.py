#!/usr/bin/env python3
"""直接测试删除事件的逻辑"""

import sys
from datetime import datetime, timedelta
from mcp_ical.ical import CalendarManager

def test_delete_logic():
    # 初始化日历管理器
    manager = CalendarManager()
    
    # 测试参数
    event_title = "打游戏"
    target_date_str = "2025-11-12"
    
    print("="  * 60)
    print("测试删除事件逻辑")
    print(f"标题: {event_title}")
    print(f"目标日期: {target_date_str}")
    print("=" * 60)
    
    # 确定搜索时间范围
    target_date = datetime.fromisoformat(target_date_str)
    start_date = target_date.replace(hour=0, minute=0, second=0)
    end_date = start_date + timedelta(days=1)
    
    print(f"\n搜索范围: {start_date} 到 {end_date}")
    
    # 列出事件
    events = manager.list_events(start_date, end_date)
    print(f"\n找到 {len(events)} 个事件:")
    for i, e in enumerate(events, 1):
        print(f"  {i}. {e.title} @ {e.start_time}")
    
    # 查找标题匹配的事件
    matching_events = [
        e for e in events 
        if event_title.lower() in e.title.lower() or e.title.lower() in event_title.lower()
    ]
    
    print(f"\n匹配 '{event_title}' 的事件: {len(matching_events)}")
    for i, e in enumerate(matching_events, 1):
        print(f"  {i}. {e.title} @ {e.start_time} (ID: {e.id[:50]}...)")
    
    if not matching_events:
        print(f"\n❌ 没有找到匹配的事件")
    elif len(matching_events) == 1:
        print(f"\n✅ 找到唯一匹配: {matching_events[0].title}")
        print(f"   可以删除此事件")
    else:
        print(f"\n⚠️  找到多个匹配，需要用户明确指定")

if __name__ == "__main__":
    test_delete_logic()
