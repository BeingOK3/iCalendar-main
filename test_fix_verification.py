"""验证 CalDAV 层的修复是否生效"""

from datetime import datetime
from mcp_ical.ical import CalendarManager
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level="DEBUG")

def test_single_day_query():
    print("\n" + "="*80)
    print("测试单天查询（应该自动扩大到2天）")
    print("="*80 + "\n")
    
    manager = CalendarManager()
    
    # 查询11月18日
    start = datetime(2025, 11, 18, 0, 0, 0)
    end = datetime(2025, 11, 19, 0, 0, 0)
    
    print(f"查询范围: {start} 到 {end}")
    print(f"时间跨度: {(end - start).total_seconds() / 86400:.2f} 天\n")
    
    events = manager.list_events(start, end)
    
    print(f"\n结果: 找到 {len(events)} 个事件")
    for event in events:
        print(f"  - {event.title} at {event.start_time}")

if __name__ == "__main__":
    test_single_day_query()
