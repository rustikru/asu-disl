from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Iterable, Optional

import pandas as pd

from core.normalization import normalize_spaces, normalize_wagon_number, strip_last_numeric_code
from core.parsers import parse_any_date, parse_any_datetime, parse_weight_kg

SPECIAL_CARGO_MARKER = "КОНТЕЙНЕРЫ СПЕЦИАЛИЗИРОВАННЫЕ ПОРОЖНИЕ СОБСТВЕННЫЕ"


def normalize_month_key(value: object, fallback_dt: Optional[datetime] = None) -> str:
    text = str(value or "").strip()
    if len(text) >= 7:
        try:
            year = int(text[:4])
            month = int(text[5:7])
            if 1 <= month <= 12:
                return f"{year:04d}-{month:02d}"
        except Exception:
            pass
    base_dt = fallback_dt or datetime.now()
    return base_dt.strftime("%Y-%m")


def month_bounds(month_key: str) -> tuple[date, date]:
    year = int(month_key[:4])
    month = int(month_key[5:7])
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def month_label(month_key: str) -> str:
    year = int(month_key[:4])
    month = int(month_key[5:7])
    months = [
        "январь", "февраль", "март", "апрель", "май", "июнь",
        "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    ]
    return f"{months[month - 1].capitalize()} {year}"


def display_day_label(day_value: date) -> str:
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"{day_value.day} {months[day_value.month - 1]} {day_value.year} г."


def _display_text(value: object, default: str) -> str:
    text = normalize_spaces(value)
    return text or default


def _first_non_empty_text(*values: object) -> str:
    for value in values:
        text = normalize_spaces(value)
        if text:
            return text
    return ""


def _cargo_sort_key(value: str) -> str:
    return normalize_spaces(value).upper().replace("Ё", "Е")


def is_special_cargo_name(value: object) -> bool:
    text = _cargo_sort_key(str(value or ""))
    return SPECIAL_CARGO_MARKER in text


def build_day_records(day_df: pd.DataFrame, month_key: str) -> list[dict[str, object]]:
    if day_df is None or day_df.empty:
        return []

    month_start, month_end = month_bounds(month_key)
    items: list[dict[str, object]] = []
    for _, row in day_df.iterrows():
        trip_dt = parse_any_datetime(row.get("trip_start_time", row.get("Дата и время начала рейса", "")))
        trip_date = trip_dt.date() if trip_dt else None
        if trip_date is None or trip_date < month_start or trip_date > month_end:
            continue

        cargo_name = _display_text(
            row.get("cargo_name_display", row.get("Наименование груза", "")),
            "Без наименования груза",
        )
        destination = _display_text(
            row.get("destination_display", row.get("Станция назначения", "")),
            "Без станции назначения",
        )
        wagon_kind_source = _first_non_empty_text(
            row.get("Род вагона", ""),
            row.get("raw_kind", ""),
            row.get("raw_kind_display", ""),
            row.get("wagon_kind", ""),
            row.get("Род подвижного состава", ""),
        )
        wagon_kind = _display_text(strip_last_numeric_code(wagon_kind_source), "Без рода вагона")
        weight_kg = parse_weight_kg(row.get("Вес груза (кг)", row.get("weight_kg_num", ""))) or 0.0
        tons = weight_kg / 1000.0
        if tons <= 0:
            continue
        items.append(
            {
                "cargo_name": cargo_name,
                "date": trip_date,
                "trip_datetime": trip_dt,
                "destination": destination,
                "wagon_kind": wagon_kind,
                "tons": tons,
                "wagon_number": normalize_wagon_number(row.get("Номер вагона", "")),
                "is_special": is_special_cargo_name(cargo_name),
            }
        )
    return items


def build_loading_month_report(
    records: Iterable[dict[str, object]],
    month_key: str,
    archive_days: Optional[set[str]] = None,
    selected_cargo_raw: Optional[str] = None,
) -> dict[str, object]:
    archive_days = archive_days or set()
    cargo_map: dict[str, dict[str, object]] = {}
    overall_tons = 0.0
    overall_wagons: set[str] = set()
    special_tons = 0.0
    special_wagons: set[str] = set()
    all_destinations: set[str] = set()
    all_days: set[date] = set()
    seen_records: set[tuple[object, ...]] = set()

    for item in records:
        cargo_name = _display_text(item.get("cargo_name"), "Без наименования груза")
        day_value = item.get("date")
        destination = _display_text(item.get("destination"), "Без станции назначения")
        wagon_kind = _display_text(item.get("wagon_kind"), "Без рода вагона")
        tons = float(item.get("tons") or 0.0)
        wagon_number = normalize_wagon_number(item.get("wagon_number", ""))
        trip_dt = item.get("trip_datetime")
        is_special = bool(item.get("is_special"))
        if not isinstance(day_value, date) or tons <= 0:
            continue

        trip_key = trip_dt.isoformat() if hasattr(trip_dt, "isoformat") and trip_dt else day_value.isoformat()
        dedupe_tail = (trip_key, cargo_name, destination, wagon_kind, round(tons, 3), bool(is_special))
        dedupe_key = (("wagon", wagon_number) if wagon_number else ("row",) + dedupe_tail) + dedupe_tail
        if dedupe_key in seen_records:
            continue
        seen_records.add(dedupe_key)

        cargo_entry = cargo_map.setdefault(
            cargo_name,
            {
                "cargo_name": cargo_name,
                "total_tons": 0.0,
                "wagon_numbers": set(),
                "anonymous_wagon_count": 0,
                "is_special": is_special,
                "records": [],
            },
        )
        cargo_entry["total_tons"] += tons
        if wagon_number:
            cargo_entry["wagon_numbers"].add(wagon_number)
        else:
            cargo_entry["anonymous_wagon_count"] += 1
        all_destinations.add(destination)
        all_days.add(day_value)

        if is_special:
            special_tons += tons
            if wagon_number:
                special_wagons.add(wagon_number)
        else:
            overall_tons += tons
            if wagon_number:
                overall_wagons.add(wagon_number)

        cargo_entry["records"].append(
            {
                "date": day_value,
                "date_label": display_day_label(day_value),
                "destination": destination,
                "wagon_kind": wagon_kind,
                "tons": tons,
                "wagon_number": wagon_number,
            }
        )

    cargo_groups: list[dict[str, object]] = []
    for cargo_name in sorted(cargo_map.keys(), key=_cargo_sort_key):
        cargo_entry = cargo_map[cargo_name]
        detail_map: dict[tuple[str, str, str], dict[str, object]] = {}
        for record in cargo_entry["records"]:
            detail_key = (
                record["date"].isoformat(),
                str(record["destination"]),
                str(record["wagon_kind"]),
            )
            detail_entry = detail_map.setdefault(
                detail_key,
                {
                    "date": record["date"],
                    "date_label": record["date_label"],
                    "destination": record["destination"],
                    "wagon_kind": record["wagon_kind"],
                    "tons": 0.0,
                    "wagon_numbers": set(),
                    "anonymous_wagon_count": 0,
                },
            )
            detail_entry["tons"] += float(record.get("tons") or 0.0)
            wagon_number = normalize_wagon_number(record.get("wagon_number", ""))
            if wagon_number:
                detail_entry["wagon_numbers"].add(wagon_number)
            else:
                detail_entry["anonymous_wagon_count"] += 1

        detail_rows = [
            {
                "date": detail_entry["date"],
                "date_label": detail_entry["date_label"],
                "destination": detail_entry["destination"],
                "wagon_kind": detail_entry["wagon_kind"],
                "wagon_count": len(detail_entry["wagon_numbers"]) + int(detail_entry["anonymous_wagon_count"]),
                "tons": detail_entry["tons"],
                "tons_label": format_tons(detail_entry["tons"]),
            }
            for _, detail_entry in sorted(
                detail_map.items(),
                key=lambda item: (item[0][0], _cargo_sort_key(item[0][1]), _cargo_sort_key(item[0][2])),
            )
        ]
        cargo_groups.append(
            {
                "cargo_name": cargo_entry["cargo_name"],
                "total_tons": cargo_entry["total_tons"],
                "total_tons_label": format_tons(cargo_entry["total_tons"]),
                "wagon_count": len(cargo_entry["wagon_numbers"]) + int(cargo_entry["anonymous_wagon_count"]),
                "is_special": cargo_entry["is_special"],
                "details": detail_rows,
            }
        )

    cargo_options = [group["cargo_name"] for group in cargo_groups]
    selected_cargo = normalize_spaces(selected_cargo_raw)
    if not selected_cargo or selected_cargo not in cargo_options:
        non_special = [group["cargo_name"] for group in cargo_groups if not group.get("is_special")]
        selected_cargo = (non_special or cargo_options or [""])[0] if cargo_options else ""

    selected_cargo_group = next((group for group in cargo_groups if group["cargo_name"] == selected_cargo), None)

    month_start, month_end = month_bounds(month_key)
    covered_days = len(archive_days)
    return {
        "month_key": month_key,
        "month_label": month_label(month_key),
        "month_start": month_start,
        "month_end": month_end,
        "cargo_groups": cargo_groups,
        "cargo_options": cargo_options,
        "selected_cargo": selected_cargo,
        "selected_cargo_group": selected_cargo_group,
        "total_tons": overall_tons,
        "total_tons_label": format_tons(overall_tons),
        "total_wagon_count": len(overall_wagons),
        "special_tons": special_tons,
        "special_tons_label": format_tons(special_tons),
        "special_wagon_count": len(special_wagons),
        "cargo_count": len(cargo_groups),
        "day_count": len(all_days),
        "destination_count": len(all_destinations),
        "covered_days": covered_days,
    }


def format_tons(value: object) -> str:
    try:
        num = float(value or 0)
    except Exception:
        return "0"
    if abs(num - round(num)) < 1e-9:
        return f"{int(round(num)):,}".replace(",", " ")
    return f"{num:,.3f}".replace(",", " ").rstrip("0").rstrip(".")
