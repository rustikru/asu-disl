from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from .mailing_models import MailingLogEntry, MailingRule, now_iso


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mailing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enabled INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    manual_filter_name TEXT NOT NULL DEFAULT '',
    to_list TEXT NOT NULL DEFAULT '',
    cc_list TEXT NOT NULL DEFAULT '',
    bcc_list TEXT NOT NULL DEFAULT '',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    schedule_type TEXT NOT NULL,
    weekdays_json TEXT NOT NULL DEFAULT '[]',
    times_json TEXT NOT NULL DEFAULT '[]',
    attach_filename_template TEXT NOT NULL DEFAULT '{report_label}_{date}.xlsx',
    add_datetime_to_subject INTEGER NOT NULL DEFAULT 0,
    last_run_at TEXT NOT NULL DEFAULT '',
    last_slot_key TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mailing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER,
    rule_name TEXT NOT NULL DEFAULT '',
    report_type TEXT NOT NULL DEFAULT '',
    to_list TEXT NOT NULL DEFAULT '',
    cc_list TEXT NOT NULL DEFAULT '',
    bcc_list TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    slot_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    attachment_name TEXT NOT NULL DEFAULT ''
);
"""


class MailingStorage:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(mailing_rules)").fetchall()}
            if "manual_filter_name" not in columns:
                conn.execute("ALTER TABLE mailing_rules ADD COLUMN manual_filter_name TEXT NOT NULL DEFAULT ''")
            conn.commit()

    def list_rules(self) -> List[MailingRule]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM mailing_rules ORDER BY id DESC").fetchall()
        return [self._row_to_rule(r) for r in rows]

    def get_rule(self, rule_id: int) -> Optional[MailingRule]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM mailing_rules WHERE id = ?", (rule_id,)).fetchone()
        return self._row_to_rule(row) if row else None

    def insert_rule(self, rule: MailingRule) -> int:
        now = now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO mailing_rules (
                    enabled, name, report_type, manual_filter_name, to_list, cc_list, bcc_list, subject, body,
                    schedule_type, weekdays_json, times_json, attach_filename_template,
                    add_datetime_to_subject, last_run_at, last_slot_key, last_status, last_error,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1 if rule.enabled else 0,
                    rule.name,
                    rule.report_type,
                    rule.manual_filter_name,
                    rule.to,
                    rule.cc,
                    rule.bcc,
                    rule.subject,
                    rule.body,
                    rule.schedule_type,
                    json.dumps(rule.normalized_weekdays(), ensure_ascii=False),
                    json.dumps(rule.normalized_times(), ensure_ascii=False),
                    rule.attach_filename_template,
                    1 if rule.add_datetime_to_subject else 0,
                    rule.last_run_at or "",
                    rule.last_slot_key,
                    rule.last_status,
                    rule.last_error,
                    now,
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update_rule(self, rule: MailingRule) -> None:
        if not rule.id:
            raise ValueError("rule.id is required for update")
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE mailing_rules
                SET enabled=?, name=?, report_type=?, manual_filter_name=?, to_list=?, cc_list=?, bcc_list=?, subject=?, body=?,
                    schedule_type=?, weekdays_json=?, times_json=?, attach_filename_template=?,
                    add_datetime_to_subject=?, last_run_at=?, last_slot_key=?, last_status=?, last_error=?, updated_at=?
                WHERE id=?
                """,
                (
                    1 if rule.enabled else 0,
                    rule.name,
                    rule.report_type,
                    rule.manual_filter_name,
                    rule.to,
                    rule.cc,
                    rule.bcc,
                    rule.subject,
                    rule.body,
                    rule.schedule_type,
                    json.dumps(rule.normalized_weekdays(), ensure_ascii=False),
                    json.dumps(rule.normalized_times(), ensure_ascii=False),
                    rule.attach_filename_template,
                    1 if rule.add_datetime_to_subject else 0,
                    rule.last_run_at or "",
                    rule.last_slot_key,
                    rule.last_status,
                    rule.last_error,
                    now,
                    rule.id,
                ),
            )
            conn.commit()

    def delete_rule(self, rule_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM mailing_rules WHERE id = ?", (rule_id,))
            conn.commit()

    def set_rule_enabled(self, rule_id: int, enabled: bool) -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE mailing_rules SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, now, rule_id),
            )
            conn.commit()

    def update_last_run(self, rule_id: int, slot_key: str, status: str, error_text: str = "") -> None:
        now = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE mailing_rules
                SET last_run_at = ?, last_slot_key = ?, last_status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, slot_key, status, error_text, now, rule_id),
            )
            conn.commit()

    def add_log(self, entry: MailingLogEntry) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO mailing_logs (
                    rule_id, rule_name, report_type, to_list, cc_list, bcc_list,
                    started_at, finished_at, slot_key, status, message, attachment_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.rule_id,
                    entry.rule_name,
                    entry.report_type,
                    entry.to,
                    entry.cc,
                    entry.bcc,
                    entry.started_at,
                    entry.finished_at,
                    entry.slot_key,
                    entry.status,
                    entry.message,
                    entry.attachment_name,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_logs(self, limit: int = 200) -> List[MailingLogEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mailing_logs ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [self._row_to_log(r) for r in rows]

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> MailingRule:
        return MailingRule(
            id=int(row["id"]),
            enabled=bool(row["enabled"]),
            name=row["name"] or "",
            report_type=row["report_type"] or "",
            manual_filter_name=(row["manual_filter_name"] or "") if "manual_filter_name" in row.keys() else "",
            to=row["to_list"] or "",
            cc=row["cc_list"] or "",
            bcc=row["bcc_list"] or "",
            subject=row["subject"] or "",
            body=row["body"] or "",
            schedule_type=row["schedule_type"] or "daily",
            weekdays=list(json.loads(row["weekdays_json"] or "[]")),
            times=list(json.loads(row["times_json"] or "[]")),
            attach_filename_template=row["attach_filename_template"] or "{report_label}_{date}.xlsx",
            add_datetime_to_subject=bool(row["add_datetime_to_subject"]),
            last_run_at=(row["last_run_at"] or "") or None,
            last_slot_key=row["last_slot_key"] or "",
            last_status=row["last_status"] or "",
            last_error=row["last_error"] or "",
            created_at=(row["created_at"] or "") or None,
            updated_at=(row["updated_at"] or "") or None,
        )

    @staticmethod
    def _row_to_log(row: sqlite3.Row) -> MailingLogEntry:
        return MailingLogEntry(
            id=int(row["id"]),
            rule_id=row["rule_id"],
            rule_name=row["rule_name"] or "",
            report_type=row["report_type"] or "",
            manual_filter_name=(row["manual_filter_name"] or "") if "manual_filter_name" in row.keys() else "",
            to=row["to_list"] or "",
            cc=row["cc_list"] or "",
            bcc=row["bcc_list"] or "",
            started_at=row["started_at"] or "",
            finished_at=row["finished_at"] or "",
            slot_key=row["slot_key"] or "",
            status=row["status"] or "",
            message=row["message"] or "",
            attachment_name=row["attachment_name"] or "",
        )
