from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from .config import TAB_APPROACH

@dataclass
class SourceState:
    df: pd.DataFrame
    source_name: str
    loaded_at: datetime
    report_dt: datetime
    file_path: Optional[str] = None
    source_kind: str = "file"
    mail_signature: Optional[str] = None
    mode: str = TAB_APPROACH

@dataclass
class MailFetchResult:
    file_path: str
    display_name: str
    message_date: Optional[datetime]
    from_value: str = ""
    subject_value: str = ""
    signature: str = ""
