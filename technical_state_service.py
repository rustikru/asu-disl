from __future__ import annotations

import json
import re
import tempfile
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from flask import Flask, redirect, request, send_file, url_for

from core.normalization import normalize_spaces, normalize_wagon_number
from core.parsers import _read_excel_robust, parse_any_datetime
from .export_service import write_single_sheet_excel
from .models import SourceState
from .technical_state_templates import TECHNICAL_STATE_BODY
from .utils import render_page


TAB_TECHNICAL_STATE = "technical_state"

TECHNICAL_STATE_COLUMNS: list[tuple[str, str]] = [
    ("Номер вагона", "BI"),
    ("Дата и время окончания рейса", "I"),
    ("Станция операции", "AF"),
    ("Станция назначения", "L"),
    ("Груз", "U"),
    ("Ранее выгруженный груз", "AE"),
    ("Состояние вагона", "BL"),
    ("Дата постройки", "BP"),
    ("Дата следующего планового ремонта", "BQ"),
    ("Вид следующего планового ремонта", "BR"),
    ("Заводской номер", "BS"),
    ("Завод-изготовитель", "BT"),
    ("Тип вагона", "BU"),
    ("Модель вагона", "BV"),
    ("Тара вагона", "BW"),
    ("Грузоподъемность вагона", "BX"),
    ("Длина по осям автосцепки", "BY"),
    ("Депо последнего кап. ремонта", "BZ"),
    ("Дата последнего кап. ремонта", "CA"),
    ("Депо последнего деп. ремонта", "CB"),
    ("Дата последнего деп. ремонта", "CC"),
    ("Дорога приписки", "CD"),
    ("Собственник", "CI"),
    ("Собственник (ОКПО)", "CJ"),
    ("Собственник (локальный код)", "CK"),
    ("Станция приписки", "CL"),
    ("Утв. дата продления срока службы", "CO"),
    ("Арендатор", "CP"),
    ("Арендатор (ОКПО)", "CQ"),
    ("Арендатор (локальный код)", "CR"),
    ("Станция приписки аренды", "CS"),
    ("Дата окончания аренды", "CT"),
    ("Срок службы вагона", "CU"),
    ("Объём кузова", "CX"),
    ("Габарит", "CY"),
    ("Тип воздухораспределителя (код)", "CZ"),
    ("Авторежим", "DA"),
    ("Авторегулятор рычажной передачи", "DB"),
    ("Тип тормоза", "DC"),
    ("Модель тележки", "DE"),
    ("Тип поглощающего аппарата", "DF"),
    ("Код модели вагона", "DK"),
    ("Оператор по доверенности", "DM"),
    ("Оператор по доверенности (ОКПО)", "DN"),
    ("Род вагона", "DO"),
    ("Количество осей вагона", "DQ"),
    ("Дней до следующего ремонта", "DT"),
]

_OPERATION_TIME_COLUMN = "AJ"


def _parse_wagon_numbers(raw_value: object) -> list[str]:
    text = str(raw_value or "")
    parts = re.split(r"[\s,;]+", text)
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        wagon = normalize_wagon_number(part)
        if wagon and wagon not in seen:
            seen.add(wagon)
            result.append(wagon)
    return result


def _excel_column_name(index: int) -> str:
    index += 1
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _find_header_row(raw_df: pd.DataFrame) -> int:
    for i in range(min(30, len(raw_df))):
        row_values = [str(v).strip() for v in raw_df.iloc[i].tolist() if pd.notna(v)]
        if "Номер вагона" in row_values and "Станция операции" in row_values:
            return i
    raise ValueError("Не удалось найти строку заголовков в Excel-файле.")


def _read_excel_by_letters(file_path: str | Path) -> pd.DataFrame:
    raw = _read_excel_robust(file_path)
    header_idx = _find_header_row(raw)
    df = raw.iloc[header_idx + 1 :].copy()
    df.columns = [_excel_column_name(i) for i in range(len(raw.columns))]
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def _format_value(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, datetime):
        if value.time() == datetime.min.time():
            return value.strftime("%d.%m.%Y")
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return str(value)
    return normalize_spaces(value)


def _load_records_from_state(state: Optional[SourceState], source_tag: str) -> list[dict]:
    if state is None or not state.file_path:
        return []
    file_path = Path(state.file_path)
    if not file_path.exists():
        return []
    try:
        frame = _read_excel_by_letters(file_path)
    except Exception:
        return []

    records: dict[str, dict] = {}
    for _, row in frame.iterrows():
        wagon_number = normalize_wagon_number(row.get("BI", ""))
        if not wagon_number:
            continue
        operation_dt = parse_any_datetime(row.get(_OPERATION_TIME_COLUMN))
        display_row = {label: _format_value(row.get(letter, "")) for label, letter in TECHNICAL_STATE_COLUMNS}
        record = {
            "wagon_number": wagon_number,
            "row": display_row,
            "cells": [display_row[label] for label, _ in TECHNICAL_STATE_COLUMNS],
            "_score": (
                operation_dt or datetime.min,
                state.report_dt or datetime.min,
                1 if source_tag == "departure" else 0,
            ),
            "_source": source_tag,
        }
        current = records.get(wagon_number)
        if current is None or record["_score"] > current["_score"]:
            records[wagon_number] = record
    return list(records.values())


def build_technical_state_snapshot(
    get_approach_state: Callable[[], Optional[SourceState]],
    get_departure_state: Callable[[], Optional[SourceState]],
) -> dict:
    approach_state = get_approach_state()
    departure_state = get_departure_state()

    combined: dict[str, dict] = {}
    for source_tag, state in (("approach", approach_state), ("departure", departure_state)):
        for item in _load_records_from_state(state, source_tag):
            wagon_number = item["wagon_number"]
            current = combined.get(wagon_number)
            if current is None or item["_score"] > current["_score"]:
                combined[wagon_number] = item

    headers = [label for label, _ in TECHNICAL_STATE_COLUMNS]
    records = sorted(
        [
            {
                "wagon_number": item["wagon_number"],
                "row": item["row"],
                "cells": item["cells"],
            }
            for item in combined.values()
        ],
        key=lambda item: (item.get("wagon_number") or "",),
    )

    source_meta_parts: list[str] = []
    if approach_state is not None:
        source_meta_parts.append(
            "Подход: "
            + (approach_state.source_name or "файл")
            + (f" • {approach_state.report_dt.strftime('%d.%m.%Y %H:%M')}" if approach_state.report_dt else "")
        )
    if departure_state is not None:
        source_meta_parts.append(
            "Отправление: "
            + (departure_state.source_name or "файл")
            + (f" • {departure_state.report_dt.strftime('%d.%m.%Y %H:%M')}" if departure_state.report_dt else "")
        )

    return {
        "headers": headers,
        "records": records,
        "source_meta": " | ".join(source_meta_parts) if source_meta_parts else "Нет загруженных справок approach/departure",
        "approach_loaded": approach_state is not None,
        "departure_loaded": departure_state is not None,
        "source_time": max(
            [state.loaded_at for state in (approach_state, departure_state) if state and state.loaded_at],
            default=None,
        ),
    }


def register_technical_state_routes(
    app: Flask,
    *,
    get_approach_state: Callable[[], Optional[SourceState]],
    get_departure_state: Callable[[], Optional[SourceState]],
    now_func: Callable[[], datetime],
    set_error: Callable[[Optional[str]], None],
    pop_error: Callable[[], Optional[str]],
    pop_success: Callable[[], Optional[str]],
) -> None:
    def _parse_filtered_rows(raw_payload: object, headers: list[str]) -> pd.DataFrame | None:
        text_payload = str(raw_payload or "").strip()
        if not text_payload:
            return None
        try:
            parsed = json.loads(text_payload)
        except Exception:
            return None
        if not isinstance(parsed, list):
            return None
        rows = [item for item in parsed if isinstance(item, dict)]
        if rows:
            frame = pd.DataFrame(rows)
        else:
            frame = pd.DataFrame(columns=headers)
        for header in headers:
            if header not in frame.columns:
                frame[header] = ""
        return frame[headers].fillna("")

    def _parse_active_filters(raw_payload: object) -> dict[int, set[str]]:
        text_payload = str(raw_payload or "").strip()
        if not text_payload:
            return {}
        try:
            parsed = json.loads(text_payload)
        except Exception:
            return {}
        if not isinstance(parsed, dict):
            return {}
        result: dict[int, set[str]] = {}
        for key, values in parsed.items():
            try:
                index = int(key)
            except Exception:
                continue
            if not isinstance(values, list):
                continue
            result[index] = {normalize_spaces(v) for v in values if normalize_spaces(v)}
        return result

    def _filter_records(records: list[dict], headers: list[str], active_filters: dict[int, set[str]]) -> list[dict]:
        if not active_filters:
            return records
        filtered: list[dict] = []
        for item in records:
            row = item.get("row") or {}
            matched = True
            for index, allowed in active_filters.items():
                if not allowed:
                    matched = False
                    break
                if index < 0 or index >= len(headers):
                    continue
                value = normalize_spaces(row.get(headers[index], ""))
                if value not in allowed:
                    matched = False
                    break
            if matched:
                filtered.append(item)
        return filtered

    def _render(search_wagon: str = "") -> str:
        snapshot = build_technical_state_snapshot(get_approach_state, get_departure_state)
        records = snapshot["records"]
        search_wagons = _parse_wagon_numbers(search_wagon)
        requested_count = len(search_wagons)
        missing_wagons: list[str] = []
        if search_wagons:
            record_map = {item.get("wagon_number"): item for item in records if item.get("wagon_number")}
            filtered_records: list[dict] = []
            for wagon in search_wagons:
                item = record_map.get(wagon)
                if item is None:
                    missing_wagons.append(wagon)
                else:
                    filtered_records.append(item)
            records = filtered_records
        source_time = snapshot["source_time"]
        return render_page(
            TECHNICAL_STATE_BODY,
            title="АСУ Подход — Техническое состояние",
            current_tab=TAB_TECHNICAL_STATE,
            headers=snapshot["headers"],
            records=records,
            total_count=len(records),
            source_meta=snapshot["source_meta"],
            source_time=source_time.strftime("Обновлено %d.%m.%Y %H:%M:%S") if isinstance(source_time, datetime) else "",
            error_message=pop_error(),
            success_message=pop_success(),
            search_wagon=search_wagon,
            search_wagons=search_wagons,
            wagon_search_summary={
                "requested_count": requested_count,
                "found_count": len(records),
                "missing_wagons": missing_wagons,
            } if requested_count > 1 else None,
        )

    @app.route("/technical-state")
    def technical_state_index():
        search_wagon = normalize_spaces(request.args.get("wagon", ""))
        return _render(search_wagon)

    @app.route("/technical-state/search")
    def technical_state_search():
        wagon_query = normalize_spaces(request.args.get("wagon", ""))
        wagon_numbers = _parse_wagon_numbers(wagon_query)
        if not wagon_numbers:
            set_error("Введите номер вагона или список номеров.")
            return redirect(url_for("technical_state_index"))
        snapshot = build_technical_state_snapshot(get_approach_state, get_departure_state)
        available = {item.get("wagon_number") for item in snapshot["records"] if item.get("wagon_number")}
        if not any(wagon in available for wagon in wagon_numbers):
            set_error("Ни один из указанных вагонов не найден.")
            return redirect(url_for("technical_state_index"))
        return redirect(url_for("technical_state_index", wagon=", ".join(wagon_numbers)))

    @app.route("/technical-state/export", methods=["POST"])
    def technical_state_export():
        snapshot = build_technical_state_snapshot(get_approach_state, get_departure_state)
        headers = snapshot["headers"]
        search_wagon = normalize_spaces(request.form.get("wagon", ""))
        search_wagons = _parse_wagon_numbers(search_wagon)
        active_filters = _parse_active_filters(request.form.get("active_filters"))
        export_df = _parse_filtered_rows(request.form.get("filtered_rows"), headers)
        if export_df is None:
            records = snapshot["records"]
            if search_wagons:
                targets = set(search_wagons)
                records = [item for item in records if item.get("wagon_number") in targets]
            records = _filter_records(records, headers, active_filters)
            export_df = pd.DataFrame([item["row"] for item in records], columns=headers)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            temp_path = Path(tmp.name)
        try:
            write_single_sheet_excel(export_df, temp_path, sheet_name="Техническое состояние")
            payload = temp_path.read_bytes()
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
        suffix = now_func().strftime("%Y-%m-%d_%H-%M")
        download_name = f"техническое_состояние_{suffix}.xlsx"
        return send_file(
            BytesIO(payload),
            as_attachment=True,
            download_name=download_name,
            max_age=0,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
