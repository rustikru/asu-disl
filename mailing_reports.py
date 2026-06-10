from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Dict, Optional


@dataclass
class MailingAttachment:
    path: Path
    download_name: str
    report_label: str


class ReportBuilderRegistry:
    """
    Реестр функций построения вложения.

    Каждая зарегистрированная функция должна принимать именованные параметры:
        app, report_type, context
    и возвращать bytes готового XLSX.
    """

    def __init__(self) -> None:
        self._builders: Dict[str, Callable[..., bytes]] = {}
        self._labels: Dict[str, str] = {}

    def register(self, report_type: str, label: str, builder: Callable[..., bytes]) -> None:
        self._builders[report_type] = builder
        self._labels[report_type] = label

    def has(self, report_type: str) -> bool:
        return report_type in self._builders

    def get_label(self, report_type: str) -> str:
        return self._labels.get(report_type, report_type)

    def build_attachment(self, *, app, report_type: str, filename_template: str, context: Optional[dict] = None) -> MailingAttachment:
        if report_type not in self._builders:
            raise ValueError(f"Для типа справки '{report_type}' не зарегистрирован builder")
        builder = self._builders[report_type]
        payload = builder(app=app, report_type=report_type, context=context or {})
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            raise ValueError(f"Builder для '{report_type}' не вернул байты XLSX")
        report_label = self.get_label(report_type)
        now = datetime.now()
        rule = context.get("rule") if isinstance(context, dict) else None
        filter_name = str(getattr(rule, "manual_filter_name", "") or "").strip()
        safe_name = filename_template.format(
            report_type=report_type,
            report_label=report_label,
            filter_name=filter_name,
            date=now.strftime("%Y-%m-%d"),
            datetime=now.strftime("%Y-%m-%d_%H-%M"),
        )
        if not safe_name.lower().endswith(".xlsx"):
            safe_name += ".xlsx"
        with NamedTemporaryFile(prefix="asu_mail_", suffix=".xlsx", delete=False) as tmp:
            tmp.write(bytes(payload))
            temp_path = Path(tmp.name)
        return MailingAttachment(path=temp_path, download_name=safe_name, report_label=report_label)
