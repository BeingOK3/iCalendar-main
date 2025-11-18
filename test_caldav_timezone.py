"""深入测试：查看 CalDAV 实际发送的 XML 请求"""

from datetime import datetime
from mcp_ical.config import get_config
import caldav
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level="DEBUG")

def test_caldav_with_timezone():
    config = get_config()
    
    client = caldav.DAVClient(
        url=config.caldav.server_url,
        username=config.caldav.username,
        password=config.caldav.password
    )
    
    principal = client.principal()
    calendars = principal.calendars()
    calendar = calendars[0]
    
    logger.info(f"测试日历: {calendar.name}")
    
    # 测试不同的时间格式
    tests = [
        {
            "name": "Naive datetime - 单天",
            "start": datetime(2025, 11, 18, 0, 0, 0),
            "end": datetime(2025, 11, 19, 0, 0, 0)
        },
        {
            "name": "Naive datetime - 单天 + 1秒",
            "start": datetime(2025, 11, 18, 0, 0, 0),
            "end": datetime(2025, 11, 19, 0, 0, 1)
        },
        {
            "name": "Naive datetime - 2天",
            "start": datetime(2025, 11, 18, 0, 0, 0),
            "end": datetime(2025, 11, 20, 0, 0, 0)
        },
        {
            "name": "Naive datetime - 7天",
            "start": datetime(2025, 11, 18, 0, 0, 0),
            "end": datetime(2025, 11, 25, 0, 0, 0)
        },
    ]
    
    for test in tests:
        logger.info("\n" + "="*80)
        logger.info(f"测试: {test['name']}")
        logger.info(f"范围: {test['start']} 到 {test['end']}")
        logger.info("="*80)
        
        results = calendar.search(
            start=test['start'],
            end=test['end'],
            event=True,
            expand=True
        )
        
        # 统计11月18日的事件
        count_1118 = 0
        for event in results:
            try:
                import vobject
                vcal = vobject.readOne(event.data)
                if hasattr(vcal, 'vevent'):
                    vevent = vcal.vevent
                    start_time = vevent.dtstart.value
                    
                    if hasattr(start_time, 'date'):
                        event_date = start_time.date()
                    else:
                        event_date = start_time
                    
                    if str(event_date) == "2025-11-18":
                        count_1118 += 1
                        logger.info(f"  ✅ {vevent.summary.value if hasattr(vevent, 'summary') else 'No title'}")
            except:
                pass
        
        logger.info(f"总结果: {len(results)} 个事件")
        logger.info(f"11月18日事件: {count_1118} 个")
        
        if count_1118 == 0:
            logger.error("❌ 未找到11月18日的事件！")
        elif count_1118 == 2:
            logger.success("✅ 找到所有2个11月18日的事件")
        else:
            logger.warning(f"⚠️ 只找到 {count_1118} 个事件（应该是2个）")

if __name__ == "__main__":
    test_caldav_with_timezone()
