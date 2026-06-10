from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from core import load_excel_as_df, normalize_wagon_number, strip_last_numeric_code
from core.parsers import parse_any_datetime
from core.normalization import normalize_spaces
from core.rules import same_station_name


def parse_iso_date(value: object) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def normalize_station_query(value: object) -> str:
    return normalize_spaces(value)


def parse_archive_wagon_numbers(value: object) -> list[str]:
    """Parse one or many wagon numbers from comma/space/newline separated text."""
    import re

    text = str(value or "")
    values: list[str] = []
    seen: set[str] = set()
    for token in re.split(r"[\s,;]+", text):
        normalized = normalize_wagon_number(token)
        if normalized and normalized not in seen:
            seen.add(normalized)
            values.append(normalized)
    return values


def archive_files_status(archive_meta_path: Path, date_from: Optional[date], date_to: Optional[date]) -> tuple[bool, bool]:
    """Return (index_exists, has_existing_file_in_period)."""
    if not archive_meta_path.exists():
        return False, False
    try:
        payload = json.loads(archive_meta_path.read_text(encoding="utf-8"))
    except Exception:
        return True, False
    if not isinstance(payload, dict):
        return True, False
    if date_from is not None and date_to is not None and date_from > date_to:
        date_from, date_to = date_to, date_from
    for tab in ("approach", "departure"):
        items = payload.get(tab, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            archive_date = parse_iso_date(item.get("archive_date"))
            if date_from is not None and archive_date is not None and archive_date < date_from:
                continue
            if date_to is not None and archive_date is not None and archive_date > date_to:
                continue
            file_path = Path(str(item.get("file_path") or ""))
            if file_path.exists():
                return True, True
    return True, False


def _first_row_value(row: pd.Series, *candidates: str) -> object:
    fallback = ""
    for index, column in enumerate(candidates):
        if column in row.index:
            value = row.get(column, "")
            if index == 0:
                fallback = value
            if normalize_spaces(value):
                return value
    return fallback


def _departure_from_acceptance_display(row: pd.Series) -> str:
    departure_value = _first_row_value(
        row,
        "Дата и время отправления со станции приема",
        "Дата и время отправления со станции приёма",
        "Дата отправления со станции приема",
        "Дата отправления со станции приёма",
        "Дата и время отправления со станции приема груза",
        "Дата и время отправления со станции приёма груза",
    )
    if not normalize_spaces(departure_value):
        return ""
    trip_start_value = row.get("Дата и время начала рейса", "")
    departure_dt = parse_any_datetime(departure_value)
    trip_start_dt = parse_any_datetime(trip_start_value)
    if departure_dt is None or trip_start_dt is None:
        return ""
    return departure_value if departure_dt >= trip_start_dt else ""


def map_archive_detail_row(row: pd.Series) -> dict[str, object]:
    arrival_destination_value = row.get("arrival_destination_display", "")
    if not normalize_spaces(arrival_destination_value):
        arrival_destination_value = row.get("Дата и время прибытия (АСОУП) на станцию назначения", "")

    archive_date = row.get("_archive_date")
    archive_date_label = archive_date.strftime("%d.%m.%Y") if isinstance(archive_date, date) else ""
    return {
        "archive_date": archive_date,
        "archive_date_label": archive_date_label,
        "source_tab": row.get("_archive_tab", ""),
        "wagon_number": row.get("Номер вагона", ""),
        "raw_kind": strip_last_numeric_code(row.get("Род вагона", "")),
        "trip_start": row.get("Дата и время начала рейса", ""),
        "trip_end": row.get("Дата и время окончания рейса", ""),
        "origin_road": row.get("Дорога отправления", ""),
        "origin_station": row.get("Станция отправления", ""),
        "destination_road": row.get("Дорога назначения", ""),
        "destination": row.get("Станция назначения", ""),
        "shipper": row.get("Грузоотправитель", row.get("Грузоотправитель (наим)", "")),
        "cargo_name": row.get("Наименование груза", ""),
        "previous_cargo": row.get("Ранее выгруженный груз", ""),
        "weight_kg": row.get("Вес груза (кг)", ""),
        "station": row.get("Станция операции", ""),
        "road": row.get("Дорога операции", ""),
        "operation": strip_last_numeric_code(row.get("Операция с вагоном", row.get("Операция", ""))),
        "operation_time": row.get("Дата и время операции", ""),
        "train_index": row.get("Индекс поезда", ""),
        "container_numbers": _first_row_value(
            row,
            "Номера контейнеров на вагоне",
            "Номера контейнеров",
            "Контейнеры",
            "№ контейнеров на вагоне",
        ),
        "norm_delivery": row.get("Нормативный срок доставки", ""),
        "distance_done": row.get("Расстояние пройденное (км)", ""),
        "distance_left": row.get("Расстояние оставшееся (км)", ""),
        "idle_time": row.get("Время простоя под последней операцией (сутки)", ""),
        "departure_from_acceptance": _departure_from_acceptance_display(row),
        "arrival_destination": arrival_destination_value,
        "wagon_state": row.get("Состояние вагона", ""),
        "owner": row.get("Собственник", ""),
    }


def search_archive_records(
    archive_meta_path: Path,
    wagon_number: str | list[str],
    station_name: str,
    date_from: Optional[date],
    date_to: Optional[date],
) -> list[dict[str, object]]:
    wagon_numbers = wagon_number if isinstance(wagon_number, list) else parse_archive_wagon_numbers(wagon_number)
    wagon_numbers = [value for value in wagon_numbers if value]
    wagon_set = set(wagon_numbers)
    station_name = normalize_station_query(station_name)
    if not wagon_set or date_from is None or date_to is None:
        return []
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    if not archive_meta_path.exists():
        return []

    try:
        payload = json.loads(archive_meta_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    result_rows: list[dict[str, object]] = []
    for tab in ("approach", "departure"):
        items = payload.get(tab, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            archive_date = parse_iso_date(item.get("archive_date"))
            if archive_date is None or archive_date < date_from or archive_date > date_to:
                continue
            file_path = Path(str(item.get("file_path") or ""))
            if not file_path.exists():
                continue
            try:
                df = load_excel_as_df(str(file_path), mode=tab)
            except Exception:
                continue
            if df.empty or "Номер вагона" not in df.columns or "Станция операции" not in df.columns:
                continue

            normalized_series = df["Номер вагона"].map(normalize_wagon_number)
            wagon_df = df[normalized_series.isin(wagon_set)].copy()
            if wagon_df.empty:
                continue
            if station_name:
                wagon_df = wagon_df[wagon_df["Станция операции"].map(lambda value: same_station_name(value, station_name))].copy()
                if wagon_df.empty:
                    continue

            wagon_df["_archive_date"] = archive_date
            wagon_df["_archive_tab"] = tab
            result_rows.extend(map_archive_detail_row(row) for _, row in wagon_df.iterrows())

    def _sort_key(item: dict[str, object]):
        archive_date = item.get("archive_date")
        archive_dt = archive_date if isinstance(archive_date, date) else date.min
        op_time = str(item.get("operation_time") or "")
        try:
            op_dt = datetime.strptime(op_time[:16], "%d.%m.%Y %H:%M")
        except Exception:
            op_dt = datetime.min
        return (archive_dt, op_dt, str(item.get("station") or ""), str(item.get("operation") or ""))

    result_rows.sort(key=_sort_key)
    return result_rows


def archive_export_frame(records: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        "Дата архива",
        "№ ваг.",
        "Род ваг.",
        "Нач. рейса",
        "Дата и время окончания рейса",
        "Дор. отпр.",
        "Ст. отпр.",
        "Дор. назн.",
        "Ст. назн.",
        "Грузоотпр.",
        "Груз",
        "Вес, кг",
        "Ст. опер.",
        "Дор. опер.",
        "Опер.",
        "Дата/время опер.",
        "Индекс поезда",
        "Контейнеры",
        "Норм. срок",
        "Пройд., км",
        "Ост., км",
        "Простой, сут.",
        "Отпр. со ст. пр.",
        "Приб. на ст. назн.",
        "Сост. ваг.",
        "Собств.",
    ]
    if not records:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(
        [
            {
                "Дата архива": item.get("archive_date_label", ""),
                "№ ваг.": item.get("wagon_number", ""),
                "Род ваг.": item.get("raw_kind", ""),
                "Нач. рейса": item.get("trip_start", ""),
                "Дата и время окончания рейса": item.get("trip_end", ""),
                "Дор. отпр.": item.get("origin_road", ""),
                "Ст. отпр.": item.get("origin_station", ""),
                "Дор. назн.": item.get("destination_road", ""),
                "Ст. назн.": item.get("destination", ""),
                "Грузоотпр.": item.get("shipper", ""),
                "Груз": item.get("cargo_name", ""),
                "Вес, кг": item.get("weight_kg", ""),
                "Ст. опер.": item.get("station", ""),
                "Дор. опер.": item.get("road", ""),
                "Опер.": item.get("operation", ""),
                "Дата/время опер.": item.get("operation_time", ""),
                "Индекс поезда": item.get("train_index", ""),
                "Контейнеры": item.get("container_numbers", ""),
                "Норм. срок": item.get("norm_delivery", ""),
                "Пройд., км": item.get("distance_done", ""),
                "Ост., км": item.get("distance_left", ""),
                "Простой, сут.": item.get("idle_time", ""),
                "Отпр. со ст. пр.": item.get("departure_from_acceptance", ""),
                "Приб. на ст. назн.": item.get("arrival_destination", ""),
                "Сост. ваг.": item.get("wagon_state", ""),
                "Собств.": item.get("owner", ""),
            }
            for item in records
        ],
        columns=columns,
    )
