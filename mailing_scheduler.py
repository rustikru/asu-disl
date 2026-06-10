from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .mailing_models import MailingLogEntry, MailingRule, MailingScheduleType, MailingSendStatus, now_iso
from .mailing_reports import ReportBuilderRegistry
from .mailing_service import OutlookMailSender
from .mailing_storage import MailingStorage


WEEKDAY_NAMES = {
    0: "ПН",
    1: "ВТ",
    2: "СР",
    3: "ЧТ",
    4: "ПТ",
    5: "СБ",
    6: "ВС",
}


class MailingScheduler:
    def __init__(
        self,
        *,
        storage: MailingStorage,
        report_registry: ReportBuilderRegistry,
        mail_sender: OutlookMailSender,
        app,
        poll_interval_seconds: int = 60,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.storage = storage
        self.report_registry = report_registry
        self.mail_sender = mail_sender
        self.app = app
        self.poll_interval_seconds = max(10, int(poll_interval_seconds))
        self.now_provider = now_provider or datetime.now
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="asu-mailing-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending()
            except Exception:
                pass
            self._stop_event.wait(self.poll_interval_seconds)

    def run_pending(self) -> None:
        now = self.now_provider()
        for rule in self.storage.list_rules():
            if not rule.enabled:
                continue
            slot_key = self._match_slot_key(rule, now)
            if not slot_key:
                continue
            if rule.last_slot_key == slot_key and (rule.last_status or "") == MailingSendStatus.SUCCESS.value:
                continue
            self.send_rule_now(rule.id, slot_key=slot_key)

    def send_rule_now(self, rule_id: int, slot_key: str = "manual") -> bool:
        rule = self.storage.get_rule(int(rule_id))
        if not rule:
            return False
        started = now_iso()
        attachment = None
        try:
            attachment = self.report_registry.build_attachment(
                app=self.app,
                report_type=rule.report_type,
                filename_template=rule.attach_filename_template,
                context={"rule": rule},
            )
            subject = self._render_subject(rule, attachment.report_label)
            self.mail_sender.send_mail(
                to=rule.to,
                cc=rule.cc,
                bcc=rule.bcc,
                subject=subject,
                body=rule.body,
                attachment_path=attachment.path,
            )
            self.storage.update_last_run(rule.id or 0, slot_key, MailingSendStatus.SUCCESS.value, "")
            self.storage.add_log(
                MailingLogEntry(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    report_type=rule.report_type,
                    to=rule.to,
                    cc=rule.cc,
                    bcc=rule.bcc,
                    started_at=started,
                    finished_at=now_iso(),
                    slot_key=slot_key,
                    status=MailingSendStatus.SUCCESS.value,
                    message="Отправлено успешно",
                    attachment_name=attachment.download_name,
                )
            )
            return True
        except Exception as exc:
            self.storage.update_last_run(rule.id or 0, slot_key, MailingSendStatus.ERROR.value, str(exc))
            self.storage.add_log(
                MailingLogEntry(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    report_type=rule.report_type,
                    to=rule.to,
                    cc=rule.cc,
                    bcc=rule.bcc,
                    started_at=started,
                    finished_at=now_iso(),
                    slot_key=slot_key,
                    status=MailingSendStatus.ERROR.value,
                    message=str(exc),
                    attachment_name=attachment.download_name if attachment else "",
                )
            )
            return False
        finally:
            if attachment and attachment.path.exists():
                try:
                    attachment.path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _render_subject(self, rule: MailingRule, report_label: str) -> str:
        now = self.now_provider()
        subject = rule.subject or report_label
        if rule.add_datetime_to_subject:
            subject = f"{subject} {now.strftime('%d.%m.%Y %H:%M')}"
        return subject

    def _match_slot_key(self, rule: MailingRule, now: datetime) -> str:
        if not self._date_matches(rule, now):
            return ""
        current_hhmm = now.strftime("%H:%M")
        if current_hhmm not in rule.normalized_times():
            return ""
        return f"{now.strftime('%Y-%m-%d')} {current_hhmm}"

    def _date_matches(self, rule: MailingRule, now: datetime) -> bool:
        schedule = rule.schedule_type or MailingScheduleType.DAILY.value
        weekday = now.weekday()
        if schedule == MailingScheduleType.DAILY.value:
            return True
        if schedule == MailingScheduleType.WEEKDAYS.value:
            return weekday <= 4
        if schedule == MailingScheduleType.SELECTED_WEEKDAYS.value:
            return weekday in rule.normalized_weekdays()
        if schedule == MailingScheduleType.MULTIPLE_TIMES_DAILY.value:
            return True
        return False


def describe_schedule(rule: MailingRule) -> str:
    schedule = rule.schedule_type or MailingScheduleType.DAILY.value
    times = ", ".join(rule.normalized_times()) or "—"
    if schedule == MailingScheduleType.DAILY.value:
        return f"Ежедневно, {times}"
    if schedule == MailingScheduleType.WEEKDAYS.value:
        return f"По будням, {times}"
    if schedule == MailingScheduleType.SELECTED_WEEKDAYS.value:
        names = ", ".join(WEEKDAY_NAMES.get(day, str(day)) for day in rule.normalized_weekdays()) or "—"
        return f"{names}, {times}"
    if schedule == MailingScheduleType.MULTIPLE_TIMES_DAILY.value:
        return f"Несколько раз в день: {times}"
    return times
