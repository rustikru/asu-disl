from __future__ import annotations

import json
import math
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlencode

import pandas as pd
from flask import Flask, redirect, request, send_file, url_for

from core import filter_detail, normalize_wagon_number, strip_last_numeric_code
from core.normalization import normalize_spaces
from core.parsers import parse_any_date, parse_any_datetime
from core.station_context import get_selected_station, normalize_station_key, station_matches
from core.rules import classify_kind, cargo_state_from_row
from .claims_ugleuralskaya_templates import (
    CLAIMS_UGLEURALSKAYA_BODY,
    CLAIMS_UGLEURALSKAYA_NORMS_BODY,
    CLAIMS_UGLEURALSKAYA_REASONS_BODY,
)
from .config import APP_TITLE, get_user_data_subdir
from .export_service import write_single_sheet_excel
from .models import SourceState
from .utils import render_page
from .shared_idle_reasons import (
    get_shared_comment,
    get_shared_comment_history,
    load_shared_comments,
    load_shared_reasons,
    save_shared_comments,
    save_shared_reasons,
    set_shared_comment,
)

CURRENT_FILE = "claims_current.json"
NORMS_FILE = "claims_norms.json"
REASONS_FILE = "claims_comment_reasons.json"
ARCHIVE_DIRNAME = "claims_ugleuralskaya_archive"
NORMS_ARCHIVE_DIRNAME = "claims_ugleuralskaya_norms_archive"
RETENTION_DAYS = 730

_KIND_RULES: list[tuple[str, str]] = [
    ("CS", "Цистерны"),
    ("MIX", "Зерновозы / цементовозы / минераловозы"),
    ("KR", "Крытые"),
    ("PV", "Полувагоны"),
    ("PL", "Платформы"),
    ("FTG", "Фитинговые платформы"),
    ("PR", "Прочие"),
]
_KIND_LABELS = {code: label for code, label in _KIND_RULES}
_OWNER_EXCLUSION = normalize_spaces('АО "МЕТАФРАКС КЕМИКАЛС"').upper().replace("Ё", "Е")

_BASE_STATION_NAME = "Углеуральская"


def _current_station_name() -> str:
    return get_selected_station(_BASE_STATION_NAME)


def _is_base_station_name(value: object) -> bool:
    return normalize_station_key(value) == normalize_station_key(_BASE_STATION_NAME)


def _record_matches_current_station(record: dict) -> bool:
    station = _current_station_name()
    raw_station = normalize_spaces(record.get("station", ""))
    if not raw_station:
        return _is_base_station_name(station)
    return station_matches(raw_station, station)
_EXPORT_COLUMNS = [
    ("wagon_number", "Вагон"),
    ("status_label", "Статус"),
    ("station", "Станция"),
    ("kind_label", "Род вагона"),
    ("shipper", "Грузоотправитель"),
    ("cargo_name", "Груз"),
    ("previous_cargo", "Ранее выгруженный груз"),
    ("owner", "Собственник"),
    ("arrived_at", "Прибыл"),
    ("departed_at", "Уехал"),
    ("fact_at", "Дата факт"),
    ("total_days", "Простой, сут."),
    ("free_days", "Бесплатно"),
    ("payable_days", "Платный"),
    ("rate_label", "Ставка, ₽/сут."),
    ("amount_label", "Сумма, ₽"),
    ("comment_period_from", "Причина с"),
    ("comment_period_to", "Причина по"),
    ("comment_text", "Комментарии"),
]


def _norm_text(value: object) -> str:
    return normalize_spaces(value).upper().replace("Ё", "Е")


def _safe_int(value: object) -> int:
    try:
        return max(int(float(str(value or 0).replace(",", "."))), 0)
    except Exception:
        return 0


def _fmt_money(value: object) -> str:
    amount = _safe_int(value)
    return f"{amount:,}".replace(",", " ")


def _fmt_date_time(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    return value.strftime("%d.%m.%Y %H:%M")


def _parse_stored_datetime(*candidates: object) -> Optional[datetime]:
    for candidate in candidates:
        text = normalize_spaces(candidate)
        if not text:
            continue
        try:
            return datetime.fromisoformat(text.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            pass
        parsed = parse_any_datetime(text)
        if parsed is not None:
            return parsed
    return None


def _kind_rule_code(raw_kind: object) -> str:
    group = classify_kind(raw_kind)
    if group in {"МВЗ", "ЗРВ", "ЦМВ"}:
        return "MIX"
    mapping = {
        "ЦС": "CS",
        "КР": "KR",
        "ПВ": "PV",
        "ПЛ": "PL",
        "ФТГ": "FTG",
    }
    return mapping.get(group, "PR")


def _kind_rule_label(code: str) -> str:
    return _KIND_LABELS.get(str(code or "").strip(), "Прочие")


def _row_class(amount: int) -> str:
    if amount <= 0:
        return "claims-row-zero"
    if amount >= 100000:
        return "claims-row-high"
    return "claims-row-penalty"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_norms() -> dict:
    return {
        "kind_rules": {code: {"free_days": 0, "rate": 0} for code, _ in _KIND_RULES},
        "shipper_rules": {},
        "cargo_rules": {},
        "previous_cargo_rules": {},
        "updated_at": "",
    }


def _load_norms(norms_path: Path) -> dict:
    norms = _load_json(norms_path, _default_norms())
    if not isinstance(norms, dict):
        norms = _default_norms()
    kind_rules = norms.get("kind_rules", {}) if isinstance(norms.get("kind_rules"), dict) else {}
    shipper_rules = norms.get("shipper_rules", {}) if isinstance(norms.get("shipper_rules"), dict) else {}
    cargo_rules = norms.get("cargo_rules", {}) if isinstance(norms.get("cargo_rules"), dict) else {}
    previous_cargo_rules = norms.get("previous_cargo_rules", {}) if isinstance(norms.get("previous_cargo_rules"), dict) else {}
    fixed_kind_rules: dict[str, dict] = {}
    for code, _label in _KIND_RULES:
        item = kind_rules.get(code, {}) if isinstance(kind_rules.get(code), dict) else {}
        fixed_kind_rules[code] = {
            "free_days": _safe_int(item.get("free_days")),
            "rate": _safe_int(item.get("rate")),
        }

    def _normalize_named_rules(raw_rules: dict) -> dict[str, dict]:
        fixed_rules: dict[str, dict] = {}
        for raw_key, item in raw_rules.items():
            if not isinstance(item, dict):
                continue
            normalized_key = _norm_text(raw_key)
            display_name = normalize_spaces(item.get("display_name") or raw_key)
            if not normalized_key or not display_name:
                continue
            fixed_rules[normalized_key] = {
                "display_name": display_name,
                "free_days": _safe_int(item.get("free_days")),
                "rate": _safe_int(item.get("rate")),
            }
        return fixed_rules

    return {
        "kind_rules": fixed_kind_rules,
        "shipper_rules": _normalize_named_rules(shipper_rules),
        "cargo_rules": _normalize_named_rules(cargo_rules),
        "previous_cargo_rules": _normalize_named_rules(previous_cargo_rules),
        "updated_at": str(norms.get("updated_at") or ""),
    }

def _save_norms(norms_path: Path, norms: dict) -> None:
    payload = _load_norms(norms_path)
    payload["kind_rules"] = norms.get("kind_rules", payload["kind_rules"])
    payload["shipper_rules"] = norms.get("shipper_rules", payload["shipper_rules"])
    payload["cargo_rules"] = norms.get("cargo_rules", payload.get("cargo_rules", {}))
    payload["previous_cargo_rules"] = norms.get("previous_cargo_rules", payload.get("previous_cargo_rules", {}))
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_json(norms_path, payload)


def _archive_norms_snapshot(norms_archive_dir: Path, norms: dict, snapshot_dt: datetime) -> None:
    payload = {
        "snapshot_date": snapshot_dt.strftime("%Y-%m-%d"),
        "snapshot_dt": snapshot_dt.isoformat(timespec="seconds"),
        **norms,
    }
    path = norms_archive_dir / f"claims_norms_{snapshot_dt.strftime('%Y-%m-%d')}.json"
    _save_json(path, payload)


def _load_reasons(reasons_path: Path) -> list[str]:
    return [normalize_spaces(item) for item in load_shared_reasons(reasons_path) if normalize_spaces(item)]


def _save_reasons(reasons_path: Path, reasons: list[str]) -> None:
    cleaned = [normalize_spaces(item) for item in reasons if normalize_spaces(item)]
    save_shared_reasons(cleaned)


def _load_current_registry(current_path: Path) -> dict[str, dict]:
    payload = _load_json(current_path, {"records": {}})
    records = payload.get("records", {}) if isinstance(payload, dict) else {}
    return records if isinstance(records, dict) else {}


def _save_current_registry(current_path: Path, records: dict[str, dict], synced_at: datetime) -> None:
    _save_json(current_path, {"synced_at": synced_at.isoformat(timespec="seconds"), "records": records})


def _records_to_export_frame(records: list[dict]) -> pd.DataFrame:
    normalized_rows: list[dict] = []
    for item in records:
        row = {}
        for source_key, export_name in _EXPORT_COLUMNS:
            value = item.get(source_key, "") if isinstance(item, dict) else ""
            row[export_name] = "" if value is None else value
        normalized_rows.append(row)
    return pd.DataFrame(normalized_rows, columns=[name for _, name in _EXPORT_COLUMNS])


def _archive_snapshot_path(archive_dir: Path, report_date: str) -> Path:
    return archive_dir / f"claims_ugleuralskaya_{report_date}.json"


def _archive_snapshot_xlsx_path(archive_dir: Path, report_date: str) -> Path:
    return archive_dir / f"claims_ugleuralskaya_{report_date}.xlsx"


def _prune_history(path: Path, now_dt: datetime) -> None:
    if not path.exists():
        return
    cutoff = now_dt.date() - timedelta(days=RETENTION_DAYS)
    for file_path in path.glob("*"):
        if not file_path.is_file():
            continue
        date_match = None
        for part in file_path.stem.split("_"):
            if len(part) == 10 and part[4] == "-" and part[7] == "-":
                date_match = part
                break
        file_date = parse_any_date(date_match) if date_match else None
        if file_date is None:
            continue
        if file_date < cutoff:
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass


def _snapshot_meta(approach_state: Optional[SourceState], departure_state: Optional[SourceState]) -> str:
    parts: list[str] = []
    if approach_state is not None:
        parts.append(
            "Подход: "
            + (approach_state.source_name or "файл")
            + (f" • {approach_state.report_dt.strftime('%d.%m.%Y %H:%M')}" if approach_state.report_dt else "")
        )
    if departure_state is not None:
        parts.append(
            "Отправление: "
            + (departure_state.source_name or "файл")
            + (f" • {departure_state.report_dt.strftime('%d.%m.%Y %H:%M')}" if departure_state.report_dt else "")
        )
    return " | ".join(parts) if parts else "Нет загруженных справок approach/departure"


def _make_cycle_id(wagon_number: str, arrived_dt: Optional[datetime], station: str = '') -> str:
    wagon = normalize_wagon_number(wagon_number)
    if not wagon or not isinstance(arrived_dt, datetime):
        return ''
    station_key = ''.join(ch for ch in _norm_text(station) if ch.isalnum())[:24]
    base = arrived_dt.strftime('%Y%m%d%H%M')
    return f"{base}|{station_key}" if station_key else base


def _same_cycle_record(previous: dict, current: dict) -> bool:
    previous_cycle = normalize_spaces(previous.get('cycle_id'))
    current_cycle = normalize_spaces(current.get('cycle_id'))
    if previous_cycle and current_cycle:
        return previous_cycle == current_cycle
    previous_arrived = _parse_stored_datetime(previous.get('arrived_at_iso'), previous.get('arrived_at'))
    current_arrived = _parse_stored_datetime(current.get('arrived_at_iso'), current.get('arrived_at'))
    return previous_arrived is not None and current_arrived is not None and previous_arrived == current_arrived


def _mark_registry_items_departed(registry: dict[str, dict], wagon_numbers: set[str], report_dt: Optional[datetime]) -> None:
    if report_dt is None:
        return
    departed_iso = report_dt.isoformat(timespec='minutes')
    departed_display = _fmt_date_time(report_dt)
    for wagon_number in wagon_numbers:
        item = registry.get(wagon_number)
        if not isinstance(item, dict):
            continue
        item['is_active'] = False
        departed_dt = _parse_stored_datetime(item.get('departed_at_iso'), item.get('departed_at'))
        if departed_dt is None:
            item['departed_at'] = departed_display
            item['departed_at_iso'] = departed_iso


def _build_live_idle_map(approach_state: Optional[SourceState]) -> dict[str, dict]:
    if approach_state is None or approach_state.df is None or approach_state.df.empty:
        return {}
    df = filter_detail(approach_state.df, report_dt=approach_state.report_dt, idle_mode="ugleuralskaya")
    live_map: dict[str, dict] = {}
    for _, row in df.iterrows():
        wagon_number = normalize_wagon_number(row.get("Номер вагона", ""))
        if not wagon_number:
            continue
        arrived_value = row.get("Дата и время окончания рейса", "")
        arrived_dt = parse_any_datetime(arrived_value)
        if arrived_dt is None:
            continue
        raw_kind = strip_last_numeric_code(row.get("Род вагона", ""))
        kind_code = _kind_rule_code(raw_kind)
        shipper = normalize_spaces(row.get("Грузоотправитель", row.get("Грузоотправитель (наим)", "")))
        cargo_name = normalize_spaces(row.get("Наименование груза", row.get("cargo_name_filter", "")))
        previous_cargo = normalize_spaces(row.get("Ранее выгруженный груз", row.get("previous_cargo_display", "")))
        owner = normalize_spaces(row.get("Собственник", ""))
        station = normalize_spaces(row.get("Станция операции", "")) or normalize_spaces(row.get("Станция назначения", ""))
        cargo_state = normalize_spaces(row.get("cargo_state", "")) or cargo_state_from_row(raw_kind, row.get("Вес груза (кг)", ""))
        live_map[wagon_number] = {
            "wagon_number": wagon_number,
            "cycle_id": _make_cycle_id(wagon_number, arrived_dt, station),
            "station": station,
            "kind_raw": raw_kind,
            "kind_code": kind_code,
            "shipper": shipper,
            "cargo_name": cargo_name,
            "previous_cargo": previous_cargo,
            "owner": owner,
            "cargo_state": cargo_state,
            "arrived_at": str(arrived_value or ""),
            "arrived_at_iso": arrived_dt.isoformat(timespec="minutes"),
            "last_seen_idle_report_dt": approach_state.report_dt.isoformat(timespec="seconds") if approach_state.report_dt else "",
            "is_active": True,
        }
    return live_map


def _build_departure_lookup(departure_state: Optional[SourceState]) -> dict[str, dict]:
    if departure_state is None or departure_state.df is None or departure_state.df.empty:
        return {}
    lookup: dict[str, dict] = {}
    for _, row in departure_state.df.iterrows():
        wagon_number = normalize_wagon_number(row.get("Номер вагона", ""))
        if not wagon_number:
            continue
        departure_value = row.get("Дата и время начала рейса", "")
        departure_dt = parse_any_datetime(departure_value)
        if departure_dt is None:
            continue
        current = lookup.get(wagon_number)
        if current is None or departure_dt > current["dt"]:
            lookup[wagon_number] = {
                "dt": departure_dt,
                "display": str(departure_value or ""),
            }
    return lookup


def _resolve_norm(record: dict, norms: dict) -> tuple[int, int]:
    wagon_number = normalize_wagon_number(record.get("wagon_number", ""))
    if _norm_text(record.get("owner")) == _OWNER_EXCLUSION or wagon_number.startswith("00"):
        return 0, 0
    shipper_rules = norms.get("shipper_rules", {}) if isinstance(norms.get("shipper_rules"), dict) else {}
    cargo_rules = norms.get("cargo_rules", {}) if isinstance(norms.get("cargo_rules"), dict) else {}
    previous_cargo_rules = norms.get("previous_cargo_rules", {}) if isinstance(norms.get("previous_cargo_rules"), dict) else {}
    kind_rules = norms.get("kind_rules", {}) if isinstance(norms.get("kind_rules"), dict) else {}
    cargo_state = normalize_spaces(record.get("cargo_state", "")).lower()
    if cargo_state == "гр":
        shipper_rule = shipper_rules.get(_norm_text(record.get("shipper")))
        if isinstance(shipper_rule, dict):
            return _safe_int(shipper_rule.get("free_days")), _safe_int(shipper_rule.get("rate"))
        cargo_rule = cargo_rules.get(_norm_text(record.get("cargo_name")))
        if isinstance(cargo_rule, dict):
            return _safe_int(cargo_rule.get("free_days")), _safe_int(cargo_rule.get("rate"))
        previous_cargo_rule = previous_cargo_rules.get(_norm_text(record.get("previous_cargo")))
        if isinstance(previous_cargo_rule, dict):
            return _safe_int(previous_cargo_rule.get("free_days")), _safe_int(previous_cargo_rule.get("rate"))
    kind_rule = kind_rules.get(str(record.get("kind_code") or "").strip())
    if isinstance(kind_rule, dict):
        return _safe_int(kind_rule.get("free_days")), _safe_int(kind_rule.get("rate"))
    return 0, 0


def _duration_days(start_dt: datetime, end_dt: datetime) -> int:
    delta_seconds = (end_dt - start_dt).total_seconds()
    if delta_seconds <= 0:
        return 0
    return int(math.ceil(delta_seconds / 86400.0))


def _report_window(period_from: Optional[date], period_to: Optional[date]) -> tuple[Optional[datetime], Optional[datetime]]:
    if period_from is None or period_to is None:
        return None, None
    start_dt = datetime.combine(period_from, datetime.min.time())
    end_dt = datetime.combine(period_to + timedelta(days=1), datetime.min.time())
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
    return start_dt, end_dt


def _overlap_window(start_a: datetime, end_a: datetime, start_b: Optional[datetime], end_b: Optional[datetime]) -> tuple[Optional[datetime], Optional[datetime]]:
    overlap_start = start_a if start_b is None else max(start_a, start_b)
    overlap_end = end_a if end_b is None else min(end_a, end_b)
    if overlap_end <= overlap_start:
        return None, None
    return overlap_start, overlap_end


def _comment_segments(shared_comments: dict[str, dict], wagon_number: str, cycle_id: str, arrived_iso: str, cycle_start_dt: datetime, cycle_end_dt: datetime) -> list[dict]:
    history = get_shared_comment_history(shared_comments, wagon_number, arrived_iso, cycle_id=cycle_id)
    if not history:
        return [{"start_dt": cycle_start_dt, "end_dt": cycle_end_dt, "comment_text": "", "updated_at": ""}]
    segments: list[dict] = []
    cursor = cycle_start_dt
    active_text = ""
    active_updated_at = ""
    for entry in history:
        effective_date = str(entry.get("effective_date") or "").strip()
        try:
            segment_start = datetime.fromisoformat(effective_date)
        except Exception:
            continue
        if segment_start < cycle_start_dt:
            active_text = normalize_spaces(entry.get("comment_text", ""))
            active_updated_at = normalize_spaces(entry.get("updated_at", ""))
            continue
        if segment_start > cursor:
            segments.append({
                "start_dt": cursor,
                "end_dt": min(segment_start, cycle_end_dt),
                "comment_text": active_text,
                "updated_at": active_updated_at,
            })
        active_text = normalize_spaces(entry.get("comment_text", ""))
        active_updated_at = normalize_spaces(entry.get("updated_at", ""))
        cursor = max(segment_start, cycle_start_dt)
        if cursor >= cycle_end_dt:
            break
    if cursor < cycle_end_dt:
        segments.append({
            "start_dt": cursor,
            "end_dt": cycle_end_dt,
            "comment_text": active_text,
            "updated_at": active_updated_at,
        })
    cleaned: list[dict] = []
    for segment in segments:
        start_dt = segment.get("start_dt")
        end_dt = segment.get("end_dt")
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime) or end_dt <= start_dt:
            continue
        if cleaned and cleaned[-1].get("comment_text") == segment.get("comment_text") and cleaned[-1].get("updated_at") == segment.get("updated_at") and cleaned[-1].get("end_dt") == start_dt:
            cleaned[-1]["end_dt"] = end_dt
            continue
        cleaned.append(segment)
    return cleaned or [{"start_dt": cycle_start_dt, "end_dt": cycle_end_dt, "comment_text": "", "updated_at": ""}]


def _period_end_date(end_dt: datetime) -> date:
    if end_dt.time() == datetime.min.time():
        return (end_dt - timedelta(days=1)).date()
    return end_dt.date()


def _display_period_end(end_dt: datetime) -> str:
    return _period_end_date(end_dt).strftime("%d.%m.%Y")


def _comment_payload_from_shared(shared_comments: dict[str, dict], wagon_number: str, arrived_iso: str, effective_date: str = '', cycle_id: str = '') -> tuple[str, str]:
    comment_text, updated_at = get_shared_comment(shared_comments, wagon_number, arrived_iso, effective_date=effective_date, cycle_id=cycle_id)
    return normalize_spaces(comment_text), normalize_spaces(updated_at)


def _archive_dates_to_date_list(raw_dates: list[str]) -> list[date]:
    result: list[date] = []
    for item in raw_dates:
        parsed = parse_any_date(item)
        if parsed is not None:
            result.append(parsed)
    return sorted({item for item in result})


def _nearest_archive_date(dates: list[date], target: date) -> Optional[date]:
    if not dates:
        return None
    return min(dates, key=lambda item: (abs((item - target).days), item))


def _select_archive_dates(dates: list[date], start: date, end: date) -> list[date]:
    if not dates:
        return []
    selected = {item for item in dates if start <= item <= end}
    before_or_equal = [item for item in dates if item <= start]
    after_or_equal = [item for item in dates if item >= end]
    if before_or_equal:
        selected.add(max(before_or_equal))
    else:
        nearest = _nearest_archive_date(dates, start)
        if nearest is not None:
            selected.add(nearest)
    if after_or_equal:
        selected.add(min(after_or_equal))
    else:
        nearest = _nearest_archive_date(dates, end)
        if nearest is not None:
            selected.add(nearest)
    if not selected:
        nearest_start = _nearest_archive_date(dates, start)
        nearest_end = _nearest_archive_date(dates, end)
        if nearest_start is not None:
            selected.add(nearest_start)
        if nearest_end is not None:
            selected.add(nearest_end)
    return sorted(selected)


def _merge_registry_with_state_records(registry: dict[str, dict], live_map: dict[str, dict], shared_comments: dict[str, dict]) -> None:
    for wagon_number, live_item in live_map.items():
        previous = registry.get(wagon_number, {}) if isinstance(registry.get(wagon_number), dict) else {}
        merged = dict(previous)
        merged.update(live_item)
        if previous and not _same_cycle_record(previous, live_item):
            merged["departed_at"] = ""
            merged["departed_at_iso"] = ""
        comment_text, comment_updated_at = _comment_payload_from_shared(shared_comments, wagon_number, normalize_spaces(merged.get("arrived_at_iso")), cycle_id=normalize_spaces(merged.get("cycle_id")))
        if comment_text or comment_updated_at:
            merged["comment_text"] = comment_text
            merged["comment_updated_at"] = comment_updated_at
        else:
            merged["comment_text"] = normalize_spaces(merged.get("comment_text", ""))
            merged["comment_updated_at"] = normalize_spaces(merged.get("comment_updated_at", ""))
        registry[wagon_number] = merged


def _apply_departure_lookup_to_registry(registry: dict[str, dict], departure_states: list[SourceState]) -> None:
    combined: dict[str, dict] = {}
    for state in departure_states:
        lookup = _build_departure_lookup(state)
        for wagon_number, item in lookup.items():
            current = combined.get(wagon_number)
            if current is None or item["dt"] > current["dt"]:
                combined[wagon_number] = item
    for wagon_number, item in registry.items():
        arrived_dt = _parse_stored_datetime(item.get("arrived_at_iso"), item.get("arrived_at"))
        departure_item = combined.get(wagon_number)
        if departure_item and (arrived_dt is None or departure_item["dt"] >= arrived_dt):
            item["departed_at"] = departure_item["display"]
            item["departed_at_iso"] = departure_item["dt"].isoformat(timespec="minutes")


def _resolve_period_dates(selected_period_from: str, selected_period_to: str) -> tuple[Optional[date], Optional[date]]:
    period_from = parse_any_date(selected_period_from) if selected_period_from else None
    period_to = parse_any_date(selected_period_to) if selected_period_to else None
    if period_from and not period_to:
        period_to = period_from
    if period_to and not period_from:
        period_from = period_to
    if period_from and period_to and period_from > period_to:
        period_from, period_to = period_to, period_from
    return period_from, period_to


def _payable_days_in_period(arrived_dt: datetime, actual_end_dt: datetime, free_days: int, period_from: date, period_to: date) -> int:
    charge_start_dt = arrived_dt + timedelta(days=max(free_days, 0))
    period_start_dt = datetime.combine(period_from, datetime.min.time())
    period_end_exclusive = datetime.combine(period_to + timedelta(days=1), datetime.min.time())
    overlap_start = max(charge_start_dt, period_start_dt)
    overlap_end = min(actual_end_dt, period_end_exclusive)
    return _duration_days(overlap_start, overlap_end)


def _intersects_period(arrived_dt: datetime, actual_end_dt: datetime, period_from: date, period_to: date) -> bool:
    period_start_dt = datetime.combine(period_from, datetime.min.time())
    period_end_exclusive = datetime.combine(period_to + timedelta(days=1), datetime.min.time())
    return min(actual_end_dt, period_end_exclusive) > max(arrived_dt, period_start_dt)


def _build_records_for_selected_period(*, current_registry: dict[str, dict], shared_comments: dict[str, dict], norms: dict, report_dt: datetime, period_from: date, period_to: date, current_approach_state: Optional[SourceState], current_departure_state: Optional[SourceState], get_archived_state: Callable[[str, str], Optional[SourceState]], list_archived_dates: Callable[[str], list[str]]) -> list[dict]:
    registry = {key: dict(value) for key, value in current_registry.items() if isinstance(value, dict) and _record_matches_current_station(value)}
    approach_dates = _archive_dates_to_date_list(list_archived_dates("approach"))
    departure_dates = _archive_dates_to_date_list(list_archived_dates("departure"))
    selected_approach_dates = _select_archive_dates(approach_dates, period_from, period_to)
    selected_departure_dates = _select_archive_dates(departure_dates, period_from, period_to)

    approach_states: list[SourceState] = []
    departure_states: list[SourceState] = []
    for archive_day in selected_approach_dates:
        state = get_archived_state("approach", archive_day.isoformat())
        if state is not None:
            approach_states.append(state)
    for archive_day in selected_departure_dates:
        state = get_archived_state("departure", archive_day.isoformat())
        if state is not None:
            departure_states.append(state)
    if not approach_states and current_approach_state is not None:
        approach_states.append(current_approach_state)
    if not departure_states and current_departure_state is not None:
        departure_states.append(current_departure_state)

    seen_cycles: set[str] = set()
    for state in sorted(approach_states, key=lambda item: item.report_dt or datetime.min):
        live_map = _build_live_idle_map(state)
        _merge_registry_with_state_records(registry, live_map, shared_comments)
        current_wagons = set(live_map)
        _mark_registry_items_departed(registry, seen_cycles - current_wagons, state.report_dt)
        seen_cycles |= current_wagons
    _apply_departure_lookup_to_registry(registry, departure_states)
    return build_claim_records(records_map=registry, norms=norms, report_dt=report_dt, period_from=period_from, period_to=period_to, shared_comments=shared_comments)


def _build_chart_rows(items: list[dict], value_key: str, label_key: str = "label", format_money: bool = False) -> list[dict]:
    max_value = max((int(item.get(value_key, 0) or 0) for item in items), default=0)
    rows: list[dict] = []
    for item in items:
        value = int(item.get(value_key, 0) or 0)
        width = 0 if max_value <= 0 else max(8, int(round(value / max_value * 100)))
        rows.append({
            "label": item.get(label_key, ""),
            "value": value,
            "value_label": _fmt_money(value) if format_money else str(value),
            "width": width,
        })
    return rows


def sync_claims_storage(
    *,
    get_approach_state: Callable[[], Optional[SourceState]],
    get_departure_state: Callable[[], Optional[SourceState]],
    get_archived_state: Optional[Callable[[str, str], Optional[SourceState]]] = None,
    list_archived_dates: Optional[Callable[[str], list[str]]] = None,
    now_func: Callable[[], datetime],
) -> None:
    storage_dir = get_user_data_subdir("claims_ugleuralskaya")
    current_path = storage_dir / CURRENT_FILE
    archive_dir = storage_dir / ARCHIVE_DIRNAME
    norms_path = storage_dir / NORMS_FILE
    norms_archive_dir = storage_dir / NORMS_ARCHIVE_DIRNAME

    approach_state = get_approach_state()
    departure_state = get_departure_state()
    synced_at = now_func()

    registry = _load_current_registry(current_path)
    shared_comments = load_shared_comments()
    live_map = _build_live_idle_map(approach_state)
    live_wagons = set(live_map)

    for wagon_number, live_item in live_map.items():
        previous = registry.get(wagon_number, {}) if isinstance(registry.get(wagon_number), dict) else {}
        same_cycle = _same_cycle_record(previous, live_item)
        merged = dict(previous)
        merged.update(live_item)
        merged["is_active"] = True
        if previous and not same_cycle:
            merged["departed_at"] = ""
            merged["departed_at_iso"] = ""
        registry[wagon_number] = merged

    missing_wagons: set[str] = set()
    for wagon_number, item in list(registry.items()):
        if not isinstance(item, dict):
            registry.pop(wagon_number, None)
            continue
        # Не закрываем и не трогаем записи других станций при работе в выбранном станционном контексте.
        if not _record_matches_current_station(item):
            continue
        if wagon_number not in live_wagons:
            missing_wagons.add(wagon_number)
    _mark_registry_items_departed(registry, missing_wagons, approach_state.report_dt if approach_state is not None and approach_state.report_dt else synced_at)

    departure_lookup = _build_departure_lookup(departure_state)
    for wagon_number, item in registry.items():
        if not _record_matches_current_station(item):
            continue
        arrived_dt = _parse_stored_datetime(item.get("arrived_at_iso"), item.get("arrived_at"))
        departure_item = departure_lookup.get(wagon_number)
        if departure_item and (arrived_dt is None or departure_item["dt"] >= arrived_dt):
            item["departed_at"] = departure_item["display"]
            item["departed_at_iso"] = departure_item["dt"].isoformat(timespec="minutes")
        report_effective_date = synced_at.date().isoformat()
        comment_text, comment_updated_at = _comment_payload_from_shared(shared_comments, wagon_number, normalize_spaces(item.get("arrived_at_iso")), report_effective_date, cycle_id=normalize_spaces(item.get("cycle_id")))
        if comment_text or comment_updated_at:
            item["comment_text"] = comment_text
            item["comment_updated_at"] = comment_updated_at
        else:
            item["comment_text"] = normalize_spaces(item.get("comment_text", ""))
            item["comment_updated_at"] = normalize_spaces(item.get("comment_updated_at", ""))

    cutoff_dt = synced_at - timedelta(days=RETENTION_DAYS)
    for wagon_number, item in list(registry.items()):
        if not isinstance(item, dict):
            registry.pop(wagon_number, None)
            continue
        if item.get("is_active"):
            continue
        anchor_dt = _parse_stored_datetime(item.get("departed_at_iso"), item.get("departed_at"), item.get("arrived_at_iso"), item.get("arrived_at"))
        if anchor_dt is not None and anchor_dt < cutoff_dt:
            registry.pop(wagon_number, None)

    _save_current_registry(current_path, registry, synced_at)

    norms = _load_norms(norms_path)
    report_dt = approach_state.report_dt if approach_state is not None and approach_state.report_dt else synced_at
    records = build_claim_records(
        records_map=registry,
        norms=norms,
        report_dt=report_dt,
        shared_comments=shared_comments,
    )
    report_date = report_dt.strftime("%Y-%m-%d")
    snapshot = {
        "report_date": report_date,
        "report_dt_label": report_dt.strftime("%d.%m.%Y %H:%M"),
        "source_meta": _snapshot_meta(approach_state, departure_state),
        "generated_at": synced_at.isoformat(timespec="seconds"),
        "records": records,
    }
    _save_json(_archive_snapshot_path(archive_dir, report_date), snapshot)
    try:
        write_single_sheet_excel(_records_to_export_frame(records), str(_archive_snapshot_xlsx_path(archive_dir, report_date)), sheet_name="Претензии")
    except Exception:
        pass
    _prune_history(archive_dir, synced_at)
    _prune_history(norms_archive_dir, synced_at)


def build_claim_records(*, records_map: dict[str, dict], norms: dict, report_dt: Optional[datetime], period_from: Optional[date] = None, period_to: Optional[date] = None, shared_comments: Optional[dict[str, dict]] = None) -> list[dict]:
    if report_dt is None:
        report_dt = datetime.now()
    shared_comments = shared_comments if isinstance(shared_comments, dict) else {}
    records: list[dict] = []
    period_mode = period_from is not None and period_to is not None
    report_window_start, report_window_end = _report_window(period_from, period_to)
    for wagon_number, source in records_map.items():
        if not isinstance(source, dict):
            continue
        if not _record_matches_current_station(source):
            continue
        owner_blocked = _norm_text(source.get("owner")) == _OWNER_EXCLUSION
        wagon_blocked = normalize_wagon_number(wagon_number).startswith("00")
        if owner_blocked or wagon_blocked:
            continue
        arrived_dt = _parse_stored_datetime(source.get("arrived_at_iso"), source.get("arrived_at"))
        if arrived_dt is None:
            continue
        departed_dt = _parse_stored_datetime(source.get("departed_at_iso"), source.get("departed_at"))
        is_departed = departed_dt is not None and departed_dt >= arrived_dt
        cycle_end_dt = departed_dt if is_departed else report_dt
        if cycle_end_dt <= arrived_dt:
            continue
        if period_mode:
            overlap_start, overlap_end = _overlap_window(arrived_dt, cycle_end_dt, report_window_start, report_window_end)
            if overlap_start is None or overlap_end is None:
                continue
        else:
            overlap_start, overlap_end = arrived_dt, cycle_end_dt
        free_days, rate = _resolve_norm(source, norms)
        free_end_dt = arrived_dt + timedelta(days=max(free_days, 0))
        charge_start_dt = free_end_dt
        kind_code = str(source.get("kind_code") or "PR").strip() or "PR"
        actual_report_display = _fmt_date_time(report_dt)
        departed_display = normalize_spaces(source.get("departed_at", "")) if is_departed else ""
        fact_display = "" if is_departed else actual_report_display
        status_code = "departed" if is_departed else "active"
        base_record = {
            "wagon_number": wagon_number,
            "status_code": status_code,
            "status_label": "Уехал" if is_departed else "На ПНП",
            "is_active": bool(source.get("is_active")),
            "station": normalize_spaces(source.get("station", "")),
            "kind_code": kind_code,
            "kind_label": _kind_rule_label(kind_code),
            "shipper": normalize_spaces(source.get("shipper", "")),
            "cargo_name": normalize_spaces(source.get("cargo_name", "")),
            "previous_cargo": normalize_spaces(source.get("previous_cargo", "")),
            "owner": normalize_spaces(source.get("owner", "")),
            "arrived_at": normalize_spaces(source.get("arrived_at", "")),
            "departed_at": departed_display,
            "fact_at": fact_display,
            "rate": rate,
            "rate_label": _fmt_money(rate),
            "cargo_state": normalize_spaces(source.get("cargo_state", "")).lower(),
            "arrived_date_key": arrived_dt.date().isoformat(),
            "arrived_at_iso": source.get("arrived_at_iso", ""),
            "cycle_id": normalize_spaces(source.get("cycle_id")),
        }
        segments = _comment_segments(shared_comments, wagon_number, normalize_spaces(source.get("cycle_id")), normalize_spaces(source.get("arrived_at_iso")), arrived_dt, cycle_end_dt) if period_mode else None
        if not segments:
            segments = [{"start_dt": overlap_start, "end_dt": overlap_end, "comment_text": normalize_spaces(source.get("comment_text", "")), "updated_at": normalize_spaces(source.get("comment_updated_at", ""))}]
        if not period_mode:
            comment_text = normalize_spaces(source.get("comment_text", ""))
            comment_updated_at = normalize_spaces(source.get("comment_updated_at", ""))
            effective_date = ((departed_dt if is_departed else report_dt).date().isoformat() if (departed_dt if is_departed else report_dt) else '')
            shared_comment_text, shared_comment_updated_at = _comment_payload_from_shared(shared_comments, wagon_number, normalize_spaces(source.get("arrived_at_iso")), effective_date, cycle_id=normalize_spaces(source.get("cycle_id")))
            if shared_comment_text or shared_comment_updated_at:
                comment_text = shared_comment_text
                comment_updated_at = shared_comment_updated_at
            total_days = _duration_days(overlap_start, overlap_end)
            free_days_part = _duration_days(*_overlap_window(arrived_dt, free_end_dt, overlap_start, overlap_end)) if free_days > 0 and _overlap_window(arrived_dt, free_end_dt, overlap_start, overlap_end)[0] else 0
            payable_days = _duration_days(*_overlap_window(charge_start_dt, cycle_end_dt, overlap_start, overlap_end)) if _overlap_window(charge_start_dt, cycle_end_dt, overlap_start, overlap_end)[0] else max(total_days - free_days_part, 0)
            amount = payable_days * rate if payable_days > 0 else 0
            record = dict(base_record)
            record.update({
                "total_days": total_days,
                "free_days": free_days_part if period_mode else free_days,
                "payable_days": payable_days,
                "amount": amount,
                "amount_label": _fmt_money(amount),
                "period_date_key": (departed_dt if is_departed else report_dt).date().isoformat(),
                "row_class": _row_class(amount),
                "comment_text": comment_text,
                "comment_updated_at": comment_updated_at,
                "comment_period_from": "",
                "comment_period_to": "",
            })
            records.append(record)
            continue

        for segment in segments:
            segment_start = segment.get("start_dt")
            segment_end = segment.get("end_dt")
            if not isinstance(segment_start, datetime) or not isinstance(segment_end, datetime):
                continue
            row_start, row_end = _overlap_window(segment_start, segment_end, report_window_start, report_window_end)
            if row_start is None or row_end is None:
                continue
            total_days = _duration_days(row_start, row_end)
            if total_days <= 0:
                continue
            free_window = _overlap_window(arrived_dt, free_end_dt, row_start, row_end)
            free_days_part = _duration_days(*free_window) if free_window[0] is not None else 0
            payable_window = _overlap_window(charge_start_dt, cycle_end_dt, row_start, row_end)
            payable_days = _duration_days(*payable_window) if payable_window[0] is not None else 0
            amount = payable_days * rate if payable_days > 0 else 0
            record = dict(base_record)
            record.update({
                "total_days": total_days,
                "free_days": free_days_part,
                "payable_days": payable_days,
                "amount": amount,
                "amount_label": _fmt_money(amount),
                "period_date_key": row_start.date().isoformat(),
                "row_class": _row_class(amount),
                "comment_text": normalize_spaces(segment.get("comment_text", "")),
                "comment_updated_at": normalize_spaces(segment.get("updated_at", "")),
                "comment_period_from": row_start.date().strftime("%d.%m.%Y"),
                "comment_period_to": _display_period_end(row_end),
                "comment_period_from_iso": row_start.date().isoformat(),
                "comment_period_to_iso": _period_end_date(row_end).isoformat(),
            })
            records.append(record)
    records.sort(key=lambda item: (-int(item.get("amount", 0) or 0), -(int(item.get("total_days", 0) or 0)), item.get("wagon_number") or "", item.get("comment_period_from_iso") or ""))
    return records


def _apply_page_filters(records: list[dict], *, selected_station: str, selected_kind_group: str, selected_shipper: str, selected_cargo_name: str, selected_previous_cargo: str, selected_period_from: str, selected_period_to: str, selected_status: str, selected_comment: str) -> list[dict]:
    filtered_records = list(records)
    if selected_station:
        target = _norm_text(selected_station)
        filtered_records = [item for item in filtered_records if _norm_text(item.get("station")) == target]
    if selected_kind_group:
        filtered_records = [item for item in filtered_records if str(item.get("kind_code") or "") == selected_kind_group]
    if selected_shipper:
        target = _norm_text(selected_shipper)
        filtered_records = [item for item in filtered_records if _norm_text(item.get("shipper")) == target]
    if selected_cargo_name:
        target = _norm_text(selected_cargo_name)
        filtered_records = [item for item in filtered_records if _norm_text(item.get("cargo_name")) == target]
    if selected_previous_cargo:
        target = _norm_text(selected_previous_cargo)
        filtered_records = [item for item in filtered_records if _norm_text(item.get("previous_cargo")) == target]
    if selected_comment:
        target = _norm_text(selected_comment)
        filtered_records = [item for item in filtered_records if _norm_text(item.get("comment_text")) == target]
    if selected_status in {"active", "departed"}:
        filtered_records = [item for item in filtered_records if item.get("status_code") == selected_status]
    return filtered_records


def _build_page_payload(*, records: list[dict], archive_date: Optional[str], source_meta: str, success_message: Optional[str], error_message: Optional[str], selected_station: str, selected_kind_group: str, selected_shipper: str, selected_cargo_name: str, selected_previous_cargo: str, selected_period_from: str, selected_period_to: str, selected_status: str, selected_comment: str, comment_reasons: list[str]) -> dict:
    kind_options = [{"value": code, "label": label} for code, label in _KIND_RULES]
    station_options = sorted({normalize_spaces(item.get("station", "")) for item in records if normalize_spaces(item.get("station", ""))})
    shipper_options = sorted({normalize_spaces(item.get("shipper", "")) for item in records if normalize_spaces(item.get("shipper", ""))})
    cargo_name_options = sorted({normalize_spaces(item.get("cargo_name", "")) for item in records if normalize_spaces(item.get("cargo_name", ""))})
    previous_cargo_options = sorted({normalize_spaces(item.get("previous_cargo", "")) for item in records if normalize_spaces(item.get("previous_cargo", ""))})
    comment_options = sorted({normalize_spaces(item.get("comment_text", "")) for item in records if normalize_spaces(item.get("comment_text", ""))})
    filtered_records = _apply_page_filters(
        records,
        selected_station=selected_station,
        selected_kind_group=selected_kind_group,
        selected_shipper=selected_shipper,
        selected_cargo_name=selected_cargo_name,
        selected_previous_cargo=selected_previous_cargo,
        selected_period_from=selected_period_from,
        selected_period_to=selected_period_to,
        selected_status=selected_status,
        selected_comment=selected_comment,
    )

    total_amount = sum(int(item.get("amount", 0) or 0) for item in filtered_records)
    penalty_count = sum(1 for item in filtered_records if int(item.get("amount", 0) or 0) > 0)
    total_count = len(filtered_records)

    summary_rows = []
    base_params = {
        "archive_date": archive_date or None,
        "station": selected_station or None,
        "shipper": selected_shipper or None,
        "cargo_name": selected_cargo_name or None,
        "previous_cargo": selected_previous_cargo or None,
        "comment": selected_comment or None,
        "period_from": selected_period_from or None,
        "period_to": selected_period_to or None,
        "status": selected_status or None,
    }
    days_chart_source: list[dict] = []
    for code, label in _KIND_RULES:
        bucket = [item for item in filtered_records if str(item.get("kind_code") or "") == code]
        amount = sum(int(item.get("amount", 0) or 0) for item in bucket)
        penalty_items = sum(1 for item in bucket if int(item.get("amount", 0) or 0) > 0)
        avg_days = int(round(sum(int(item.get("total_days", 0) or 0) for item in bucket) / len(bucket))) if bucket else 0
        params = {k: v for k, v in {**base_params, "kind_group": code}.items() if v}
        summary_rows.append({
            "code": code,
            "label": label,
            "count": len(bucket),
            "penalty_count": penalty_items,
            "amount": amount,
            "amount_label": _fmt_money(amount),
            "row_class": _row_class(amount),
            "link": url_for("claims_ugleuralskaya_index") + ("?" + urlencode(params) if params else ""),
        })
        days_chart_source.append({"label": label, "days": avg_days})

    amount_chart_rows = _build_chart_rows(summary_rows, "amount", format_money=True)
    days_chart_rows = _build_chart_rows(days_chart_source, "days")

    selected_work_station = get_selected_station("Углеуральская")

    return {
        "title": f"{APP_TITLE} — Претензии на {selected_work_station}",
        "app_title": APP_TITLE,
        "current_tab": "station_idle",
        "source_meta": source_meta,
        "archive_date": archive_date or "",
        "records": filtered_records,
        "summary_rows": summary_rows,
        "total_amount_label": _fmt_money(total_amount),
        "total_count": total_count,
        "penalty_count": penalty_count,
        "zero_penalty_count": total_count - penalty_count,
        "station_options": station_options,
        "kind_options": kind_options,
        "shipper_options": shipper_options,
        "cargo_name_options": cargo_name_options,
        "previous_cargo_options": previous_cargo_options,
        "comment_options": comment_options,
        "selected_station": selected_station,
        "selected_work_station": selected_work_station,
        "selected_kind_group": selected_kind_group,
        "selected_shipper": selected_shipper,
        "selected_cargo_name": selected_cargo_name,
        "selected_previous_cargo": selected_previous_cargo,
        "selected_period_from": selected_period_from,
        "selected_period_to": selected_period_to,
        "selected_status": selected_status,
        "selected_comment": selected_comment,
        "success_message": success_message,
        "error_message": error_message,
        "amount_chart_rows": amount_chart_rows,
        "days_chart_rows": days_chart_rows,
        "comment_reasons": comment_reasons,
    }


def register_claims_ugleuralskaya_routes(
    app: Flask,
    *,
    get_approach_state: Callable[[], Optional[SourceState]],
    get_departure_state: Callable[[], Optional[SourceState]],
    get_archived_state: Callable[[str, str], Optional[SourceState]],
    list_archived_dates: Callable[[str], list[str]],
    now_func: Callable[[], datetime],
    set_success: Callable[[Optional[str]], None],
    pop_success: Callable[[], Optional[str]],
    set_error: Callable[[Optional[str]], None],
    pop_error: Callable[[], Optional[str]],
) -> None:
    storage_dir = get_user_data_subdir("claims_ugleuralskaya")
    current_path = storage_dir / CURRENT_FILE
    norms_path = storage_dir / NORMS_FILE
    reasons_path = storage_dir / REASONS_FILE
    archive_dir = storage_dir / ARCHIVE_DIRNAME
    norms_archive_dir = storage_dir / NORMS_ARCHIVE_DIRNAME

    def _load_live_records(selected_period_from: str, selected_period_to: str) -> tuple[list[dict], str]:
        sync_claims_storage(
            get_approach_state=get_approach_state,
            get_departure_state=get_departure_state,
            now_func=now_func,
        )
        approach_state = get_approach_state()
        departure_state = get_departure_state()
        report_dt = approach_state.report_dt if approach_state is not None and approach_state.report_dt else now_func()
        registry = _load_current_registry(current_path)
        norms = _load_norms(norms_path)
        shared_comments = load_shared_comments()
        period_from, period_to = _resolve_period_dates(selected_period_from, selected_period_to)
        if period_from and period_to:
            records = _build_records_for_selected_period(
                current_registry=registry,
                shared_comments=shared_comments,
                norms=norms,
                report_dt=report_dt,
                period_from=period_from,
                period_to=period_to,
                current_approach_state=approach_state,
                current_departure_state=departure_state,
                get_archived_state=get_archived_state,
                list_archived_dates=list_archived_dates,
            )
        else:
            records = build_claim_records(records_map=registry, norms=norms, report_dt=report_dt, shared_comments=shared_comments)
        return records, _snapshot_meta(approach_state, departure_state)

    def _render_index(records: list[dict], archive_date: Optional[str], source_meta: str):
        return render_page(
            CLAIMS_UGLEURALSKAYA_BODY,
            **_build_page_payload(
                records=records,
                archive_date=archive_date,
                source_meta=source_meta,
                success_message=pop_success(),
                error_message=pop_error(),
                selected_station=normalize_spaces(request.args.get("station")),
                selected_kind_group=normalize_spaces(request.args.get("kind_group")),
                selected_shipper=normalize_spaces(request.args.get("shipper")),
                selected_cargo_name=normalize_spaces(request.args.get("cargo_name")),
                selected_previous_cargo=normalize_spaces(request.args.get("previous_cargo")),
                selected_period_from=normalize_spaces(request.args.get("period_from")),
                selected_period_to=normalize_spaces(request.args.get("period_to")),
                selected_status=normalize_spaces(request.args.get("status")),
                selected_comment=normalize_spaces(request.args.get("comment")),
                comment_reasons=_load_reasons(reasons_path),
            ),
        )

    @app.route("/claims-ugleuralskaya")
    def claims_ugleuralskaya_index():
        archive_date = normalize_spaces(request.args.get("archive_date"))
        if archive_date:
            snapshot = _load_json(_archive_snapshot_path(archive_dir, archive_date), {})
            records = snapshot.get("records", []) if isinstance(snapshot, dict) else []
            source_meta = str(snapshot.get("source_meta") or "Архив претензий") if isinstance(snapshot, dict) else "Архив претензий"
            return _render_index(records if isinstance(records, list) else [], archive_date, source_meta)

        records, source_meta = _load_live_records(
            normalize_spaces(request.args.get("period_from")),
            normalize_spaces(request.args.get("period_to")),
        )
        return _render_index(records, None, source_meta)

    @app.route("/claims-ugleuralskaya/export")
    def claims_ugleuralskaya_export():
        archive_date = normalize_spaces(request.args.get("archive_date"))
        if archive_date:
            snapshot = _load_json(_archive_snapshot_path(archive_dir, archive_date), {})
            records = snapshot.get("records", []) if isinstance(snapshot, dict) else []
        else:
            records, _source_meta = _load_live_records(
                normalize_spaces(request.args.get("period_from")),
                normalize_spaces(request.args.get("period_to")),
            )
        filtered = _apply_page_filters(
            list(records) if isinstance(records, list) else [],
            selected_station=normalize_spaces(request.args.get("station")),
            selected_kind_group=normalize_spaces(request.args.get("kind_group")),
            selected_shipper=normalize_spaces(request.args.get("shipper")),
            selected_cargo_name=normalize_spaces(request.args.get("cargo_name")),
            selected_previous_cargo=normalize_spaces(request.args.get("previous_cargo")),
            selected_period_from=normalize_spaces(request.args.get("period_from")),
            selected_period_to=normalize_spaces(request.args.get("period_to")),
            selected_status=normalize_spaces(request.args.get("status")),
            selected_comment=normalize_spaces(request.args.get("comment")),
        )
        frame = _records_to_export_frame(filtered)
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp.close()
        write_single_sheet_excel(frame, temp.name, sheet_name="Претензии")
        stamp = now_func().strftime("%Y%m%d_%H%M%S")
        safe_station = re.sub(r'[^0-9A-Za-zА-Яа-яЁё_-]+', '_', get_selected_station("Углеуральская")).strip('_') or "station"
        return send_file(temp.name, as_attachment=True, download_name=f"asu_podhod_Претензии_на_{safe_station}_{stamp}.xlsx")

    @app.route("/claims-ugleuralskaya/norms")
    def claims_ugleuralskaya_norms():
        norms = _load_norms(norms_path)
        kind_rules = [
            {
                "code": code,
                "label": label,
                "free_days": norms["kind_rules"].get(code, {}).get("free_days", 0),
                "rate": norms["kind_rules"].get(code, {}).get("rate", 0),
            }
            for code, label in _KIND_RULES
        ]
        def _sorted_named_rules(group_name: str) -> list[dict]:
            return sorted(
                [
                    {
                        "name": item.get("display_name", key),
                        "free_days": _safe_int(item.get("free_days")),
                        "rate": _safe_int(item.get("rate")),
                        "rate_label": _fmt_money(item.get("rate")),
                    }
                    for key, item in norms.get(group_name, {}).items()
                    if isinstance(item, dict)
                ],
                key=lambda item: _norm_text(item.get("name")),
            )
        shipper_rules = _sorted_named_rules("shipper_rules")
        cargo_rules = _sorted_named_rules("cargo_rules")
        previous_cargo_rules = _sorted_named_rules("previous_cargo_rules")
        return render_page(
            CLAIMS_UGLEURALSKAYA_NORMS_BODY,
            title=f"{APP_TITLE} — Нормативы претензий",
            kind_rules=kind_rules,
            shipper_rules=shipper_rules,
            cargo_rules=cargo_rules,
            previous_cargo_rules=previous_cargo_rules,
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/claims-ugleuralskaya/norms/kinds/save", methods=["POST"])
    def claims_ugleuralskaya_norms_save_kinds():
        norms = _load_norms(norms_path)
        kind_rules = dict(norms.get("kind_rules", {}))
        for code, _label in _KIND_RULES:
            kind_rules[code] = {
                "free_days": _safe_int(request.form.get(f"free_days_{code}")),
                "rate": _safe_int(request.form.get(f"rate_{code}")),
            }
        norms["kind_rules"] = kind_rules
        _save_norms(norms_path, norms)
        _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
        sync_claims_storage(
            get_approach_state=get_approach_state,
            get_departure_state=get_departure_state,
            now_func=now_func,
        )
        set_success("Нормативы по роду вагона сохранены.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/shipper/upsert", methods=["POST"])
    def claims_ugleuralskaya_norms_upsert_shipper():
        name = normalize_spaces(request.form.get("shipper_name"))
        if not name:
            set_error("Укажите грузоотправителя.")
            return redirect(url_for("claims_ugleuralskaya_norms"))
        norms = _load_norms(norms_path)
        rules = dict(norms.get("shipper_rules", {}))
        rules[_norm_text(name)] = {
            "display_name": name,
            "free_days": _safe_int(request.form.get("free_days")),
            "rate": _safe_int(request.form.get("rate")),
        }
        norms["shipper_rules"] = rules
        _save_norms(norms_path, norms)
        _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
        sync_claims_storage(
            get_approach_state=get_approach_state,
            get_departure_state=get_departure_state,
            now_func=now_func,
        )
        set_success("Норматив грузоотправителя сохранён.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/shipper/delete", methods=["POST"])
    def claims_ugleuralskaya_norms_delete_shipper():
        name = normalize_spaces(request.form.get("shipper_name"))
        key = _norm_text(name)
        norms = _load_norms(norms_path)
        rules = dict(norms.get("shipper_rules", {}))
        if key in rules:
            rules.pop(key, None)
            norms["shipper_rules"] = rules
            _save_norms(norms_path, norms)
            _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
            sync_claims_storage(
                get_approach_state=get_approach_state,
                get_departure_state=get_departure_state,
                now_func=now_func,
            )
            set_success("Норматив грузоотправителя удалён.")
        else:
            set_error("Норматив грузоотправителя не найден.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/cargo/upsert", methods=["POST"])
    def claims_ugleuralskaya_norms_upsert_cargo():
        name = normalize_spaces(request.form.get("cargo_name"))
        if not name:
            set_error("Укажите груз.")
            return redirect(url_for("claims_ugleuralskaya_norms"))
        norms = _load_norms(norms_path)
        rules = dict(norms.get("cargo_rules", {}))
        rules[_norm_text(name)] = {"display_name": name, "free_days": _safe_int(request.form.get("free_days")), "rate": _safe_int(request.form.get("rate"))}
        norms["cargo_rules"] = rules
        _save_norms(norms_path, norms)
        _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
        sync_claims_storage(get_approach_state=get_approach_state, get_departure_state=get_departure_state, now_func=now_func)
        set_success("Норматив по грузу сохранён.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/cargo/delete", methods=["POST"])
    def claims_ugleuralskaya_norms_delete_cargo():
        name = normalize_spaces(request.form.get("cargo_name"))
        key = _norm_text(name)
        norms = _load_norms(norms_path)
        rules = dict(norms.get("cargo_rules", {}))
        if key in rules:
            rules.pop(key, None)
            norms["cargo_rules"] = rules
            _save_norms(norms_path, norms)
            _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
            sync_claims_storage(get_approach_state=get_approach_state, get_departure_state=get_departure_state, now_func=now_func)
            set_success("Норматив по грузу удалён.")
        else:
            set_error("Норматив по грузу не найден.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/previous-cargo/upsert", methods=["POST"])
    def claims_ugleuralskaya_norms_upsert_previous_cargo():
        name = normalize_spaces(request.form.get("previous_cargo_name"))
        if not name:
            set_error("Укажите ранее выгруженный груз.")
            return redirect(url_for("claims_ugleuralskaya_norms"))
        norms = _load_norms(norms_path)
        rules = dict(norms.get("previous_cargo_rules", {}))
        rules[_norm_text(name)] = {"display_name": name, "free_days": _safe_int(request.form.get("free_days")), "rate": _safe_int(request.form.get("rate"))}
        norms["previous_cargo_rules"] = rules
        _save_norms(norms_path, norms)
        _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
        sync_claims_storage(get_approach_state=get_approach_state, get_departure_state=get_departure_state, now_func=now_func)
        set_success("Норматив по ранее выгруженному грузу сохранён.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/norms/previous-cargo/delete", methods=["POST"])
    def claims_ugleuralskaya_norms_delete_previous_cargo():
        name = normalize_spaces(request.form.get("previous_cargo_name"))
        key = _norm_text(name)
        norms = _load_norms(norms_path)
        rules = dict(norms.get("previous_cargo_rules", {}))
        if key in rules:
            rules.pop(key, None)
            norms["previous_cargo_rules"] = rules
            _save_norms(norms_path, norms)
            _archive_norms_snapshot(norms_archive_dir, _load_norms(norms_path), now_func())
            sync_claims_storage(get_approach_state=get_approach_state, get_departure_state=get_departure_state, now_func=now_func)
            set_success("Норматив по ранее выгруженному грузу удалён.")
        else:
            set_error("Норматив по ранее выгруженному грузу не найден.")
        return redirect(url_for("claims_ugleuralskaya_norms"))

    @app.route("/claims-ugleuralskaya/reasons")
    def claims_ugleuralskaya_reasons():
        return render_page(
            CLAIMS_UGLEURALSKAYA_REASONS_BODY,
            title=f"{APP_TITLE} — Комментарии претензий",
            reasons=_load_reasons(reasons_path),
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/claims-ugleuralskaya/reasons/add", methods=["POST"])
    def claims_ugleuralskaya_reasons_add():
        reason = normalize_spaces(request.form.get("reason"))
        reasons = _load_reasons(reasons_path)
        if reason and reason.casefold() not in {item.casefold() for item in reasons}:
            reasons.append(reason)
            _save_reasons(reasons_path, reasons)
            set_success("Комментарий добавлен.")
        return redirect(url_for("claims_ugleuralskaya_reasons"))

    @app.route("/claims-ugleuralskaya/reasons/update", methods=["POST"])
    def claims_ugleuralskaya_reasons_update():
        old_reason = normalize_spaces(request.form.get("old_reason"))
        new_reason = normalize_spaces(request.form.get("new_reason"))
        reasons = _load_reasons(reasons_path)
        updated: list[str] = []
        seen: set[str] = set()
        for item in reasons:
            value = new_reason if item == old_reason and new_reason else item
            folded = value.casefold()
            if not value or folded in seen:
                continue
            seen.add(folded)
            updated.append(value)
        _save_reasons(reasons_path, updated)
        set_success("Комментарий обновлён.")
        return redirect(url_for("claims_ugleuralskaya_reasons"))

    @app.route("/claims-ugleuralskaya/reasons/delete", methods=["POST"])
    def claims_ugleuralskaya_reasons_delete():
        reason = normalize_spaces(request.form.get("reason"))
        reasons = [item for item in _load_reasons(reasons_path) if item != reason]
        _save_reasons(reasons_path, reasons)
        set_success("Комментарий удалён.")
        return redirect(url_for("claims_ugleuralskaya_reasons"))

    @app.route("/claims-ugleuralskaya/comment", methods=["POST"])
    def claims_ugleuralskaya_comment_save():
        wagon_number = normalize_wagon_number(request.form.get("wagon_number"))
        arrived_at_iso = normalize_spaces(request.form.get("arrived_at_iso"))
        cycle_id = normalize_spaces(request.form.get("cycle_id"))
        comment_text = normalize_spaces(request.form.get("comment_text"))
        next_url = request.form.get("next") or url_for("claims_ugleuralskaya_index")
        registry = _load_current_registry(current_path)
        item = registry.get(wagon_number)
        if not isinstance(item, dict):
            set_error("Запись для комментария не найдена.")
            return redirect(next_url)
        actual_arrived_at_iso = normalize_spaces(item.get("arrived_at_iso"))
        actual_cycle_id = normalize_spaces(item.get("cycle_id"))
        if cycle_id and actual_cycle_id and actual_cycle_id != cycle_id:
            set_error("Запись комментария устарела. Обновите вкладку.")
            return redirect(next_url)
        if (not cycle_id) and arrived_at_iso and actual_arrived_at_iso and actual_arrived_at_iso != arrived_at_iso:
            set_error("Запись комментария устарела. Обновите вкладку.")
            return redirect(next_url)
        arrived_at_iso = actual_arrived_at_iso or arrived_at_iso
        cycle_id = actual_cycle_id or cycle_id
        effective_date = normalize_spaces(request.form.get("comment_effective_date")) or now_func().date().isoformat()
        updated_at = now_func().strftime("%d.%m.%Y %H:%M") if comment_text else ""
        shared_comments = load_shared_comments()
        shared_comments = set_shared_comment(shared_comments, wagon_number, arrived_at_iso, comment_text, updated_at, effective_date=effective_date, cycle_id=cycle_id)
        save_shared_comments(shared_comments)
        item["comment_text"] = comment_text
        item["comment_updated_at"] = updated_at
        item["arrived_at_iso"] = arrived_at_iso
        item["cycle_id"] = cycle_id
        registry[wagon_number] = item
        _save_current_registry(current_path, registry, now_func())
        sync_claims_storage(
            get_approach_state=get_approach_state,
            get_departure_state=get_departure_state,
            now_func=now_func,
        )
        set_success("Комментарий сохранён.")
        return redirect(next_url)
