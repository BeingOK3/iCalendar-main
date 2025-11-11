"""mcp_ical.models
------------------

数据模型层：定义事件（Event）、循环规则（RecurrenceRule）以及用于创建/更新事件的
Pydantic 请求模型（CreateEventRequest, UpdateEventRequest）。

此模块负责将 CalDAV / iCalendar（vobject）格式与项目内部的 Python 对象互相转换，
并提供类型验证与灵活的日期时间解析器，便于上层 `caldav_client.py` 和 `server.py`
以统一的方式处理事件数据。

主要导出：
- Frequency, Weekday: 枚举类型，用于表示重复频率与星期
- RecurrenceRule: Pydantic 模型，解析与校验 RRULE
- Event: dataclass，表示解析后的事件（含原始 CalDAV 对象引用）
- CreateEventRequest / UpdateEventRequest: Pydantic 模型，供 API 层（MCP）使用

注意：模块内既使用 Pydantic（用于外部输入验证）也使用 dataclass（用于内部轻量对象），
两者按需使用以兼顾性能与校验能力。
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Annotated, Self, Optional

from caldav import CalendarObjectResource
from loguru import logger
from pydantic import BaseModel, BeforeValidator, Field, model_validator
import vobject


class Frequency(IntEnum):
    DAILY = 0
    WEEKLY = 1
    MONTHLY = 2
    YEARLY = 3


class Weekday(IntEnum):
    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 3
    WEDNESDAY = 4
    THURSDAY = 5
    FRIDAY = 6
    SATURDAY = 7


def convert_datetime(v):
    """Flexible datetime converter used by Pydantic validators.

    支持的输入类型：
    - 已经是 datetime 对象：直接返回
    - ISO8601 字符串（例如 "2025-11-07T14:30:00"）：使用 datetime.fromisoformat 解析
    - iCalendar 字符串格式（例如 "20251107T143000Z"）：使用 datetime.strptime 解析
    - vobject 包装对象（具有 .value 属性）：提取 .value

    设计目标：对外部输入（MCP/JSON/CalDAV）提供宽容的日期时间解析，
    避免因为小的格式差异导致上层频繁抛出错误。若无法解析则返回原值交由
    Pydantic 的后续校验处理并产生日志警告。
    """
    if isinstance(v, datetime):
        # 已是 datetime，直接返回
        return v

    if isinstance(v, str):
        # 首先尝试解析为 ISO 格式，兼容常见的 JSON 时间字符串
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            try:
                # 回退：尝试解析 iCalendar 常见的 UTC 字符串格式 YYYYMMDDTHHMMSSZ
                return datetime.strptime(v, "%Y%m%dT%H%M%SZ")
            except ValueError:
                # 解析失败时记录警告，并返回原始值（由 Pydantic 抛出更明确的错误）
                logger.warning(f"Could not parse datetime string: {v}")
                return v

    if hasattr(v, 'value'):
        # vobject 中的日期时间对象通常包装在 .value 属性内，提取实际 datetime
        return v.value

    # 未知类型：记录调试信息并返回原值，交由上层校验处理
    logger.debug(f"Unrecognized datetime type: {type(v)}, value: {v}")
    return v


# FlexibleDateTime 是一个带有预验证器的类型别名，用于 Pydantic 模型中。
# 在 Pydantic 进行字段校验之前，会调用 convert_datetime 做宽容解析，
# 支持 ISO 字符串、iCal 格式字符串以及 vobject 的日期对象。
FlexibleDateTime = Annotated[datetime, BeforeValidator(convert_datetime)]


class RecurrenceRule(BaseModel):
    """表示重复规则（RRULE）的 Pydantic 模型。

    字段说明：
    - frequency: 重复频率（DAILY/WEEKLY/...）
    - interval: 重复间隔（例如每 2 周 -> interval=2）
    - end_date: 可选的结束日期（与 occurrence_count 互斥）
    - occurrence_count: 可选的出现次数
    - days_of_week: 可选的星期列表（用于 WEEKLY/按星期重复场景）

    该模型负责：
    1. 校验互斥条件（end_date 与 occurrence_count 不能同时出现）
    2. 提供从 iCalendar RRULE 字符串解析到模型实例的工厂方法
    """
    frequency: Frequency
    interval: int = Field(default=1, ge=1)
    end_date: FlexibleDateTime | None = None
    occurrence_count: int | None = None
    days_of_week: list[Weekday] | None = None

    @model_validator(mode="after")
    def validate_end_conditions(self) -> Self:
        """在模型初始化后验证互斥条件。

        如果同时提供了 end_date 与 occurrence_count，抛出 ValueError。
        这个校验保证了生成的 RRULE 在语义上是明确的。
        """
        if self.end_date is not None and self.occurrence_count is not None:
            raise ValueError("Only one of end_date or occurrence_count can be set")
        return self

    @classmethod
    def from_ical_string(cls, rrule_str: str) -> Self:
        """将 iCalendar 风格的 RRULE 字符串解析为 RecurrenceRule 实例。

        支持的 RRULE 片段包括：FREQ、INTERVAL、BYDAY、UNTIL、COUNT。
        解析策略为：将字符串按 ';' 分割，提取键值对并映射到相应字段。
        注意：UNTIL 以 UTC 字符串（YYYYMMDDTHHMMSSZ）或日期（YYYYMMDD）格式解析。
        """
        parts = {}
        for part in rrule_str.split(';'):
            if '=' in part:
                key, value = part.split('=', 1)
                parts[key] = value

        frequency_map = {
            'DAILY': 0,
            'WEEKLY': 1,
            'MONTHLY': 2,
            'YEARLY': 3
        }

        frequency = frequency_map.get(parts.get('FREQ', 'DAILY'), 0)
        interval = int(parts.get('INTERVAL', '1'))

        end_date = None
        occurrence_count = None

        if 'UNTIL' in parts:
            # UNTIL 示例：YYYYMMDDTHHMMSSZ 或 YYYYMMDD
            until_str = parts['UNTIL']
            try:
                if 'T' in until_str:
                    end_date = datetime.strptime(until_str, "%Y%m%dT%H%M%SZ")
                else:
                    end_date = datetime.strptime(until_str, "%Y%m%d")
            except ValueError:
                # 解析失败则忽略 UNTIL，由调用方决定如何处理
                pass
        elif 'COUNT' in parts:
            occurrence_count = int(parts['COUNT'])

        days_of_week = None
        if 'BYDAY' in parts:
            weekday_map = {
                'SU': 1, 'MO': 2, 'TU': 3, 'WE': 4, 'TH': 5, 'FR': 6, 'SA': 7
            }
            days = []
            for day in parts['BYDAY'].split(','):
                if day in weekday_map:
                    days.append(weekday_map[day])
            if days:
                days_of_week = days

        return cls(
            frequency=frequency,
            interval=interval,
            end_date=end_date,
            occurrence_count=occurrence_count,
            days_of_week=days_of_week
        )


@dataclass
class Event:
    """事件的内部表示（轻量 dataclass）。

    该类表示从 CalDAV/vobject 解析得到的事件信息，并携带原始 CalDAV 对象
   （`_raw_event`）以便后续操作（例如更新或删除）可以直接调用底层 API。

    字段含义参见属性定义：title/start_time/end_time/identifier 等。
    """
    title: str
    start_time: FlexibleDateTime
    end_time: FlexibleDateTime
    identifier: str
    
    @property
    def id(self) -> str:
        """提供 id 属性作为 identifier 的别名，便于 Web API 使用"""
        return self.identifier
    
    @property
    def description(self) -> str | None:
        """提供 description 属性作为 notes 的别名，便于 Web API 使用"""
        return self.notes
    
    calendar_name: str | None = None
    location: str | None = None
    notes: str | None = None
    alarms_minutes_offsets: list[int] | None = None
    url: str | None = None
    all_day: bool = False
    has_alarms: bool = False
    organizer: str | None = None
    attendees: list[str] | None = None
    last_modified: FlexibleDateTime | None = None
    recurrence_rule: RecurrenceRule | None = None
    _raw_event: Optional[CalendarObjectResource] = None  # Store the original CalDAV event

    @staticmethod
    def _extract_event_id(caldav_event: CalendarObjectResource) -> str:
        """从 CalDAV 事件中提取字符串形式的唯一标识符"""
        event_id = getattr(caldav_event, 'id', None)
        
        # 如果 id 是一个对象（如 URL 对象），尝试获取其字符串表示
        if event_id is not None:
            if hasattr(event_id, 'url_raw'):
                return str(event_id.url_raw)
            elif hasattr(event_id, '__str__'):
                return str(event_id)
        
        # 回退到 URL
        event_url = getattr(caldav_event, 'url', None)
        if event_url:
            return str(event_url)
        
        # 最后回退：使用数据的哈希值
        return str(hash(str(caldav_event.data)))
    
    @classmethod
    def from_caldav_event(cls, caldav_event: CalendarObjectResource) -> "Event":
        """从 CalDAV 返回的 CalendarObjectResource 构建 Event 实例。

        逻辑要点：
        - 支持 caldav_event.data 为字符串或已解析的 vobject 对象
        - 提取 vevent 的常见字段（summary/dtstart/dtend/description/location/url）
        - 解析 VALARM（提醒）并将其转换为分钟偏移列表
        - 解析 RRULE（重复规则），并委托给 RecurrenceRule.from_ical_string
        - 提取 organizer/attendee 等信息

        返回的 Event 会保留原始 caldav_event（存储在 _raw_event）以便后续 CRUD 操作复用。
        """
        event_id = cls._extract_event_id(caldav_event)
        logger.debug(f"Parsing event data for event {event_id}")

        # Handle both string and vobject data
        event_data = caldav_event.data
        if isinstance(event_data, str):
            # Parse string data into vobject
            vcal = vobject.readOne(event_data)
            logger.debug("Parsed string data into vobject")
        else:
            vcal = event_data
            logger.debug("Using existing vobject data")

        if not hasattr(vcal, 'vevent'):
            logger.error(f"Event data has no vevent component. Data type: {type(event_data)}")
            logger.debug(f"Event data content: {str(event_data)[:500]}...")
            raise ValueError(f"Event data has no vevent component")

        vevent = vcal.vevent
        logger.debug(f"Successfully extracted vevent for event {event_id}")

        # Basic properties
        title = getattr(vevent, 'summary', '').value if hasattr(vevent, 'summary') and vevent.summary else 'No Title'
        start_time = getattr(vevent, 'dtstart', '').value if hasattr(vevent, 'dtstart') and vevent.dtstart else None
        end_time = getattr(vevent, 'dtend', '').value if hasattr(vevent, 'dtend') and vevent.dtend else None
        
        # 统一时区: 将所有带时区的 datetime 转换为 naive datetime
        if start_time and hasattr(start_time, 'tzinfo') and start_time.tzinfo:
            start_time = start_time.replace(tzinfo=None)
        if end_time and hasattr(end_time, 'tzinfo') and end_time.tzinfo:
            end_time = end_time.replace(tzinfo=None)

        location = None
        if hasattr(vevent, 'location') and vevent.location:
            location = vevent.location.value

        notes = None
        if hasattr(vevent, 'description') and vevent.description:
            notes = vevent.description.value

        url = None
        if hasattr(vevent, 'url') and vevent.url:
            url = vevent.url.value

        # Check if all-day event
        all_day = False
        if hasattr(vevent, 'dtstart') and vevent.dtstart:
            all_day = hasattr(vevent.dtstart, 'value_param') and vevent.dtstart.value_param == 'DATE'

        # Process alarms: 将 VALARM 的 TRIGGER 解析为分钟偏移量（例如 -PT15M -> 15）
        alarms = []
        if hasattr(vevent, 'valarm'):
            for alarm in vevent.getChildren():
                if alarm.name == 'VALARM' and hasattr(alarm, 'trigger') and alarm.trigger:
                    trigger = str(alarm.trigger.value)
                    # Parse trigger like "-PT15M" (15 minutes before)
                    match = re.match(r'-PT(\d+)([HM])', trigger)
                    if match:
                        amount = int(match.group(1))
                        unit = match.group(2)
                        if unit == 'H':
                            alarms.append(amount * 60)
                        else:  # M for minutes
                            alarms.append(amount)

        # Process recurrence rule
        recurrence = None
        if hasattr(vevent, 'rrule') and vevent.rrule:
            rrule_str = str(vevent.rrule.value)
            recurrence = RecurrenceRule.from_ical_string(rrule_str)

        # Get organizer
        organizer = None
        if hasattr(vevent, 'organizer') and vevent.organizer:
            organizer = vevent.organizer.value

        # Process attendees
        attendees = []
        if hasattr(vevent, 'attendee'):
            for attendee in vevent.getChildren():
                if attendee.name == 'ATTENDEE' and hasattr(attendee, 'cn') and attendee.cn:
                    attendees.append(attendee.cn.value)

        try:
            # Get last modified
            last_modified = None
            if hasattr(vevent, 'last_modified') and vevent.last_modified:
                last_modified = vevent.last_modified.value

            return cls(
                title=title,
                start_time=start_time,
                end_time=end_time,
                calendar_name=caldav_event.parent.name if hasattr(caldav_event, 'parent') and caldav_event.parent else None,
                location=location,
                notes=notes,
                url=url,
                all_day=all_day,
                alarms_minutes_offsets=alarms if alarms else None,
                recurrence_rule=recurrence,
                organizer=organizer,
                attendees=attendees if attendees else None,
                last_modified=last_modified,
                identifier=cls._extract_event_id(caldav_event),
                _raw_event=caldav_event,
            )

        except Exception as e:
            logger.error(f"Failed to parse CalDAV event {event_id}: {e}")
            logger.debug(f"CalDAV event data: {caldav_event.data}")
            raise ValueError(f"Failed to parse event {event_id}: {e}") from e

    def __str__(self) -> str:
        """返回事件的可读字符串表示，供 MCP 层直接返回给用户。

        该方法将事件的关键字段格式化为多行字符串，包含：标题、标识符、时间、日历、位置、提醒、组织者、参与者和重复信息。
        设计目标是为自然语言界面提供足够的上下文信息，使用户在不查看原始对象的情况下也能理解事件内容。
        """
        attendees_list = ", ".join(self.attendees) if self.attendees else "None"
        alarms_list = ", ".join(map(str, self.alarms_minutes_offsets)) if self.alarms_minutes_offsets else "None"

        recurrence_info = "No recurrence"
        if self.recurrence_rule:
            frequency_names = {0: "DAILY", 1: "WEEKLY", 2: "MONTHLY", 3: "YEARLY"}
            recurrence_info = (
                f"Recurrence: {frequency_names.get(self.recurrence_rule.frequency, 'UNKNOWN')}, "
                f"Interval: {self.recurrence_rule.interval}, "
                f"End Date: {self.recurrence_rule.end_date or 'N/A'}, "
                f"Occurrences: {self.recurrence_rule.occurrence_count or 'N/A'}"
            )

        return (
            f"Event: {self.title},\n"
            f" - Identifier: {self.identifier},\n"
            f" - Start Time: {self.start_time},\n"
            f" - End Time: {self.end_time},\n"
            f" - Calendar: {self.calendar_name or 'N/A'},\n"
            f" - Location: {self.location or 'N/A'},\n"
            f" - Notes: {self.notes or 'N/A'},\n"
            f" - Alarms (minutes before): {alarms_list},\n"
            f" - URL: {self.url or 'N/A'},\n"
            f" - All Day Event?: {self.all_day},\n"
            f" - Organizer: {self.organizer or 'N/A'},\n"
            f" - Attendees: {attendees_list},\n"
            f" - {recurrence_info}\n"
        )


class CreateEventRequest(BaseModel):
    """用于创建事件的 Pydantic 模型（输入验证）。

    说明：该模型用于 MCP 工具 `create_event` 的参数绑定。Pydantic 会自动将
    来自 MCP 的 JSON/参数转换为此模型实例并执行类型校验。字段含义：
    - title/start_time/end_time: 必填，表示事件基本时间信息
    - calendar_name: 可选，若省略则使用默认日历（由 CalDAVManager 决定）
    - alarms_minutes_offsets: 可选的提醒偏移（以分钟为单位）
    - recurrence_rule: 可选的 RecurrenceRule，用于创建重复事件
    """
    title: str
    start_time: datetime
    end_time: datetime
    calendar_name: str | None = None
    location: str | None = None
    notes: str | None = None
    alarms_minutes_offsets: list[int] | None = None
    url: str | None = None
    all_day: bool = False
    recurrence_rule: RecurrenceRule | None = None


class UpdateEventRequest(BaseModel):
    """用于更新事件的 Pydantic 模型（部分更新）。

    所有字段均为可选。MCP 层在调用 update_event 时只需传入需要修改的字段。
    注意：字段为 None 的含义是“不做修改”，而不是将字段清空。
    """
    title: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    calendar_name: str | None = None
    location: str | None = None
    notes: str | None = None
    alarms_minutes_offsets: list[int] | None = None
    url: str | None = None
    all_day: bool | None = None
    recurrence_rule: RecurrenceRule | None = None
