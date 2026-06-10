from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import List, Optional


class MailingScheduleType(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    SELECTED_WEEKDAYS = "selected_weekdays"
    MULTIPLE_TIMES_DAILY = "multiple_times_daily"


class MailingSendStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class MailingRule:
    id: Optional[int] = None
    enabled: bool = True
    name: str = ""
    report_type: str = "approach"
    manual_filter_name: str = ""
    to: str = ""
    cc: str = ""
    bcc: str = ""
    subject: str = ""
    body: str = ""
    schedule_type: str = MailingScheduleType.DAILY.value
    weekdays: List[int] = field(default_factory=list)
    times: List[str] = field(default_factory=lambda: ["08:00"])
    attach_filename_template: str = "{report_label}_{date}.xlsx"
    add_datetime_to_subject: bool = False
    last_run_at: Optional[str] = None
    last_slot_key: str = ""
    last_status: str = ""
    last_error: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def normalized_times(self) -> List[str]:
        clean: List[str] = []
        for value in self.times:
            item = (value or "").strip()
            if not item:
                continue
            if len(item) == 4 and item[1] == ":":
                item = f"0{item}"
            clean.append(item)
        return sorted(set(clean))

    def normalized_weekdays(self) -> List[int]:
        return sorted({int(x) for x in self.weekdays if str(x).strip() != ""})


@dataclass
class MailingLogEntry:
    id: Optional[int] = None
    rule_id: Optional[int] = None
    rule_name: str = ""
    report_type: str = ""
    to: str = ""
    cc: str = ""
    bcc: str = ""
    started_at: str = ""
    finished_at: str = ""
    slot_key: str = ""
    status: str = MailingSendStatus.SUCCESS.value
    message: str = ""
    attachment_name: str = ""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def parse_time_hhmm(value: str) -> time:
    raw = (value or "").strip()
    if len(raw) == 4 and raw[1] == ":":
        raw = f"0{raw}"
    hour_str, minute_str = raw.split(":", 1)
    return time(hour=int(hour_str), minute=int(minute_str))
