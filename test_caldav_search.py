"""测试 CalDAV search 方法的行为，找出短时间范围查询问题的根本原因"""

from datetime import datetime, timedelta
from mcp_ical.config import get_config
import caldav
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level="DEBUG")

def test_caldav_search():
    # 加载配置
    config = get_config()
    
    # 连接到 CalDAV 服务器
    client = caldav.DAVClient(
        url=config.caldav.server_url,
        username=config.caldav.username,
        password=config.caldav.password
    )
    
    principal = client.principal()
    calendars = principal.calendars()
    
    if not calendars:
        logger.error("No calendars found!")
        return
    
    # 使用第一个日历进行测试
    calendar = calendars[0]
    logger.info(f"Testing with calendar: {calendar.name}")
    
    # 测试1: 查询单天（11月18日）
    logger.info("\n" + "="*80)
    logger.info("测试1: 查询单天 (2025-11-18)")
    logger.info("="*80)
    
    single_day_start = datetime(2025, 11, 18, 0, 0, 0)
    single_day_end = datetime(2025, 11, 19, 0, 0, 0)
    
    logger.info(f"查询范围: {single_day_start} 到 {single_day_end}")
    
    # 查看实际发送的请求
    logger.info("调用 calendar.search()...")
    results_single = calendar.search(
        start=single_day_start,
        end=single_day_end,
        event=True,
        expand=True
    )
    
    logger.info(f"返回结果数量: {len(results_single)}")
    for event in results_single:
        logger.info(f"  - {event.id}")
    
    # 测试2: 查询30天范围
    logger.info("\n" + "="*80)
    logger.info("测试2: 查询30天范围 (2025-11-03 到 2025-12-18)")
    logger.info("="*80)
    
    extended_start = datetime(2025, 11, 3, 0, 0, 0)
    extended_end = datetime(2025, 12, 18, 0, 0, 0)
    
    logger.info(f"查询范围: {extended_start} 到 {extended_end}")
    logger.info("调用 calendar.search()...")
    
    results_extended = calendar.search(
        start=extended_start,
        end=extended_end,
        event=True,
        expand=True
    )
    
    logger.info(f"返回结果数量: {len(results_extended)}")
    
    # 过滤出11月18日的事件
    filtered = []
    for event in results_extended:
        try:
            # 解析事件数据获取时间
            import vobject
            vcal = vobject.readOne(event.data)
            if hasattr(vcal, 'vevent'):
                vevent = vcal.vevent
                start_time = vevent.dtstart.value
                
                # 转换为datetime进行比较
                if hasattr(start_time, 'date'):
                    event_date = start_time.date() if hasattr(start_time, 'date') else start_time
                else:
                    event_date = start_time
                
                target_date = single_day_start.date()
                
                if str(event_date) == str(target_date):
                    filtered.append(event)
                    logger.info(f"  - {vevent.summary.value if hasattr(vevent, 'summary') else 'No title'} at {start_time}")
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
    
    logger.info(f"\n在30天范围内找到11月18日的事件数量: {len(filtered)}")
    
    # 对比结果
    logger.info("\n" + "="*80)
    logger.info("结果对比")
    logger.info("="*80)
    logger.info(f"单天查询返回: {len(results_single)} 个事件")
    logger.info(f"30天查询后过滤: {len(filtered)} 个事件")
    
    if len(results_single) != len(filtered):
        logger.error(f"⚠️ 发现问题！单天查询缺少了 {len(filtered) - len(results_single)} 个事件！")
        logger.error("这就是为什么我们需要扩大查询范围的根本原因。")
    else:
        logger.success("✅ 两种方法返回的事件数量一致")
    
    # 测试3: 查看 calendar.events() 返回什么
    logger.info("\n" + "="*80)
    logger.info("测试3: calendar.events() 方法（不带时间范围）")
    logger.info("="*80)
    
    all_events = calendar.events()
    logger.info(f"calendar.events() 返回: {len(all_events)} 个事件")
    
    # 过滤11月18日
    filtered_all = []
    for event in all_events:
        try:
            import vobject
            vcal = vobject.readOne(event.data)
            if hasattr(vcal, 'vevent'):
                vevent = vcal.vevent
                start_time = vevent.dtstart.value
                
                if hasattr(start_time, 'date'):
                    event_date = start_time.date() if hasattr(start_time, 'date') else start_time
                else:
                    event_date = start_time
                
                target_date = single_day_start.date()
                
                if str(event_date) == str(target_date):
                    filtered_all.append(event)
                    logger.info(f"  - {vevent.summary.value if hasattr(vevent, 'summary') else 'No title'} at {start_time}")
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
    
    logger.info(f"\n在所有事件中找到11月18日的事件数量: {len(filtered_all)}")

if __name__ == "__main__":
    test_caldav_search()
