from __future__ import annotations

import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode
from typing import Callable, Optional

import pandas as pd
from flask import Flask, redirect, request, send_file, url_for

from core import (
    CARGO_ORDER,
    STATION_IDLE_BUCKETS,
    STATION_IDLE_UGL_CATEGORY_ORDER,
    filter_detail,
    normalize_wagon_number,
    strip_last_numeric_code,
    whole_calendar_days,
)
from core.dataframe_ops import get_station_idle_bucket
from core.parsers import parse_any_datetime
from core.station_context import get_selected_station
from .config import APP_TITLE, TAB_APPROACH, get_user_data_subdir
from .export_service import write_single_sheet_excel
from .idle_comments_templates import (
    IDLE_COMMENTS_DETAIL_BODY,
    IDLE_COMMENTS_INDEX_BODY,
    IDLE_COMMENTS_REASONS_BODY,
)
from .models import SourceState
from .utils import render_page
from .shared_idle_reasons import (
    comment_storage_key,
    get_shared_comment,
    load_shared_comments,
    load_shared_reasons,
    prune_shared_comments_to_keys,
    save_shared_comments,
    save_shared_reasons,
    set_shared_comment,
)

CURRENT_FILE = "idle_comments_current.json"
REASONS_FILE = "idle_comment_reasons.json"
ARCHIVE_DIRNAME = "idle_comments_archive"
SNAPSHOT_DIRNAME = "idle_comments_snapshots"


def _inject_detail_row_highlight(html: str) -> str:
    if not html:
        return html
    marker = "asu-detail-row-highlight"
    if marker in html:
        return html
    snippet = """
<style id="asu-detail-row-highlight">
.detail-table tbody tr{cursor:pointer;}
.detail-table tbody tr.asu-selected-row td{background:#fff6bf !important; box-shadow: inset 0 1px 0 #ead36c, inset 0 -1px 0 #ead36c;}
</style>
<script id="asu-detail-row-highlight-script">
(function(){
  function bindDetailRowHighlight(){
    var rows=document.querySelectorAll('.detail-table tbody tr');
    if(!rows.length){return;}
    rows.forEach(function(row){
      if(row.dataset.highlightBound==='1'){return;}
      row.dataset.highlightBound='1';
      row.addEventListener('click', function(event){
        var target=event.target;
        if(target && target.closest('a, button, input, select, textarea, label')){return;}
        rows.forEach(function(item){ if(item!==row){ item.classList.remove('asu-selected-row'); } });
        row.classList.toggle('asu-selected-row');
      });
    });
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', bindDetailRowHighlight);
  } else {
    bindDetailRowHighlight();
  }
})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", snippet + "</body>", 1)
    return html + snippet


def register_idle_comments_routes(
    app: Flask,
    *,
    get_approach_state: Callable[[], Optional[SourceState]],
    now_func: Callable[[], datetime],
    set_success: Callable[[Optional[str]], None],
    pop_success: Callable[[], Optional[str]],
    set_error: Callable[[Optional[str]], None],
    pop_error: Callable[[], Optional[str]],
) -> None:
    archive_dir = get_user_data_subdir(ARCHIVE_DIRNAME)
    snapshot_dir = get_user_data_subdir(SNAPSHOT_DIRNAME)
    current_path = get_user_data_subdir("comments") / CURRENT_FILE
    reasons_path = get_user_data_subdir("comments") / REASONS_FILE



    DETAIL_EXPORT_COLUMNS = [
        ("wagon_number", "№ ваг."),
        ("raw_kind", "Род ваг."),
        ("trip_start", "Нач. рейса"),
        ("trip_end", "Дата и время окончания рейса"),
        ("origin_road", "Дор. отпр."),
        ("origin_station", "Ст. отпр."),
        ("destination_road", "Дор. назн."),
        ("destination", "Ст. назн."),
("cargo_name", "Груз"),
        ("previous_cargo", "Ранее выгруженный груз"),
        ("weight_kg", "Вес, кг"),
        ("station", "Ст. опер."),
        ("operation", "Опер."),
        ("operation_time", "Дата/время опер."),
        ("idle_time", "Простой, сут."),
        ("comment_updated_at", "Дата и время"),
        ("comment_text", "Примечание"),
    ]

    def detail_export_frame(rows: list[dict]) -> pd.DataFrame:
        normalized_rows: list[dict] = []
        for item in rows:
            row = {}
            for source_key, export_name in DETAIL_EXPORT_COLUMNS:
                value = item.get(source_key, "") if isinstance(item, dict) else ""
                row[export_name] = "" if value is None else value
            normalized_rows.append(row)
        return pd.DataFrame(normalized_rows, columns=[export_name for _, export_name in DETAIL_EXPORT_COLUMNS])

    def load_json(path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_reasons() -> list[str]:
        return load_shared_reasons(reasons_path)

    def save_reasons(items: list[str]) -> None:
        save_shared_reasons(items)

    def current_report_date_key(state: SourceState) -> str:
        report_dt = state.report_dt or now_func()
        return report_dt.strftime("%Y-%m-%d")

    def load_current_comments() -> dict[str, dict]:
        return load_shared_comments(current_path)

    def save_current_comments(comments: dict[str, dict]) -> None:
        save_shared_comments(comments)

    def _build_base_rows(state: SourceState) -> list[dict]:
        df = filter_detail(state.df, report_dt=state.report_dt, idle_mode="ugleuralskaya")
        rows: list[dict] = []
        for _, row in df.iterrows():
            wagon_number = normalize_wagon_number(row.get("Номер вагона", ""))
            if not wagon_number:
                continue
            idle_reference = row.get("Дата и время прибытия (АСОУП) на станцию назначения", "") or row.get("Дата и время операции", "")
            idle_days = whole_calendar_days(idle_reference, state.report_dt)
            trip_end_value = str(row.get("Дата и время окончания рейса", "") or "")
            trip_end_dt = parse_any_datetime(trip_end_value)
            rows.append(
                {
                    "wagon_number": wagon_number,
                    "raw_kind": strip_last_numeric_code(row.get("Род вагона", "")),
                    "trip_start": str(row.get("Дата и время начала рейса", "") or ""),
                    "trip_end": trip_end_value,
                    "arrived_at_iso": trip_end_dt.isoformat(timespec="minutes") if trip_end_dt is not None else "",
                    "origin_road": str(row.get("Дорога отправления", "") or ""),
                    "origin_station": str(row.get("Станция отправления", "") or ""),
                    "destination_road": str(row.get("Дорога назначения", "") or ""),
                    "destination": str(row.get("Станция назначения", "") or ""),
                    "cargo_name": str(row.get("Наименование груза", "") or ""),
                    "weight_kg": row.get("Вес груза (кг)", ""),
                    "station": str(row.get("Станция операции", "") or ""),
                    "operation": strip_last_numeric_code(row.get("Операция с вагоном", row.get("Операция", ""))),
                    "operation_time": str(row.get("Дата и время операции", "") or ""),
                    "idle_time": row.get("Время простоя под последней операцией (сутки)", ""),
                    "kind_group": str(row.get("kind_group", "") or ""),
                    "cargo_state": str(row.get("cargo_state", "") or ""),
                    "idle_bucket": str(get_station_idle_bucket(idle_days) or ""),
                    "comment_updated_at": "",
                    "comment_text": "",
                }
            )
        return rows

    def build_current_snapshot() -> dict:
        state = get_approach_state()
        if state is None:
            return {"rows": [], "report_date": "", "source_name": "Файл ещё не загружен", "source_time": ""}

        current_comments = load_current_comments()
        base_rows = _build_base_rows(state)
        live_wagons = {item["wagon_number"] for item in base_rows}
        new_comments: dict[str, dict] = {}
        for item in base_rows:
            wagon_key = item["wagon_number"]
            comment_text, comment_updated_at = get_shared_comment(current_comments, wagon_key, item.get("arrived_at_iso", ""))
            item["comment_text"] = comment_text
            item["comment_updated_at"] = comment_updated_at
            if item["comment_text"] or item["comment_updated_at"]:
                new_comments[comment_storage_key(wagon_key, item.get("arrived_at_iso", ""))] = {
                    "wagon_number": wagon_key,
                    "arrived_at_iso": item.get("arrived_at_iso", ""),
                    "comment_text": item["comment_text"],
                    "updated_at": item["comment_updated_at"],
                }
        # current shared comments are written only on explicit save actions
        snapshot = {
            "report_date": current_report_date_key(state),
            "report_dt_label": state.report_dt.strftime("%d.%m.%Y %H:%M") if state.report_dt else "",
            "source_name": state.source_name,
            "source_time": state.loaded_at.strftime("Обновлено %d.%m.%Y %H:%M:%S") if state.loaded_at else "",
            "rows": base_rows,
        }
        return snapshot

    def snapshot_path(report_date: str) -> Path:
        return snapshot_dir / f"idle_comments_{report_date}.json"

    def archive_excel_path(report_date: str) -> Path:
        return archive_dir / f"idle_comments_{report_date}.xlsx"

    def save_snapshot(snapshot: dict) -> None:
        report_date = str(snapshot.get("report_date") or "")
        if not report_date:
            return
        save_json(snapshot_path(report_date), snapshot)
        rows = snapshot.get("rows", []) if isinstance(snapshot, dict) else []
        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                "wagon_number", "raw_kind", "trip_start", "trip_end", "origin_road", "origin_station", "destination_road",
                "destination", "cargo_name", "previous_cargo", "weight_kg", "station", "operation", "operation_time", "idle_time",
                "comment_updated_at", "comment_text",
            ])
        export_df = df.rename(columns={
            "wagon_number": "№ ваг.",
            "raw_kind": "Род ваг.",
            "trip_start": "Нач. рейса",
            "trip_end": "Дата и время окончания рейса",
            "origin_road": "Дор. отпр.",
            "origin_station": "Ст. отпр.",
            "destination_road": "Дор. назн.",
            "destination": "Ст. назн.",
            "cargo_name": "Груз",
            "previous_cargo": "Ранее выгруженный груз",
            "weight_kg": "Вес, кг",
            "station": "Ст. опер.",
            "operation": "Опер.",
            "operation_time": "Дата/время опер.",
            "idle_time": "Простой, сут.",
            "comment_updated_at": "Дата и время",
            "comment_text": "Примечание",
        })
        archive_dir.mkdir(parents=True, exist_ok=True)
        write_single_sheet_excel(export_df, str(archive_excel_path(report_date)), sheet_name="Простой с комментариями")

    def load_snapshot(report_date: str) -> Optional[dict]:
        data = load_json(snapshot_path(report_date), None)
        return data if isinstance(data, dict) else None

    def parse_snapshot_date(value: Optional[str]) -> Optional[date]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except Exception:
            return None

    def available_snapshot_dates(date_from: Optional[date], date_to: Optional[date]) -> list[tuple[date, str]]:
        result: list[tuple[date, str]] = []
        if not snapshot_dir.exists():
            return result
        for path in snapshot_dir.glob("idle_comments_*.json"):
            suffix = path.stem.replace("idle_comments_", "", 1)
            current = parse_snapshot_date(suffix)
            if current is None:
                continue
            if date_from and current < date_from:
                continue
            if date_to and current > date_to:
                continue
            result.append((current, suffix))
        result.sort(key=lambda item: item[0], reverse=True)
        return result

    def render_idle_comments_detail(
        *,
        records: list[dict],
        filter_caption: str,
        archive_mode: bool,
        archive_date: str = "",
        idle_bucket: Optional[str] = None,
        kind: Optional[str] = None,
        cargo: Optional[str] = None,
        show_report_date: bool = False,
        search_wagon: str = "",
        search_date_from: str = "",
        search_date_to: str = "",
        back_url: Optional[str] = None,
        export_archive_date: str = "",
    ) -> str:
        detail_html = render_page(
            IDLE_COMMENTS_DETAIL_BODY,
            title=f"{APP_TITLE} — комментарии к простою",
            records=records,
            total_count=len(records),
            filter_caption=filter_caption,
            archive_date=archive_date,
            archive_mode=archive_mode,
            idle_bucket=idle_bucket,
            kind=kind,
            cargo=cargo,
            reasons=load_reasons(),
            success_message=pop_success(),
            error_message=pop_error(),
            show_report_date=show_report_date,
            search_wagon=search_wagon,
            search_date_from=search_date_from,
            search_date_to=search_date_to,
            back_url=back_url,
            export_archive_date=export_archive_date,
        )
        return _inject_detail_row_highlight(detail_html)

    def summary_rows_from_snapshot(snapshot: dict) -> list[dict]:
        rows = snapshot.get("rows", []) if isinstance(snapshot, dict) else []
        frame = pd.DataFrame(rows)
        selected_station = get_selected_station("Углеуральская")
        result: list[dict] = [{
            "level": "total",
            "label": selected_station,
            "counts": {cat: {cargo: 0 for cargo in CARGO_ORDER} for cat in STATION_IDLE_UGL_CATEGORY_ORDER},
            "idle_bucket": None,
        }]
        for bucket_key, bucket_label in STATION_IDLE_BUCKETS:
            result.append({
                "level": "bucket",
                "label": bucket_label,
                "counts": {cat: {cargo: 0 for cargo in CARGO_ORDER} for cat in STATION_IDLE_UGL_CATEGORY_ORDER},
                "idle_bucket": bucket_key,
            })
        if frame.empty:
            return result
        for target in result:
            current = frame.copy()
            if target["idle_bucket"]:
                current = current[current["idle_bucket"] == target["idle_bucket"]]
            for category in STATION_IDLE_UGL_CATEGORY_ORDER:
                if category == "Всего":
                    by_cat = current
                else:
                    by_cat = current[current["kind_group"] == category]
                for cargo in CARGO_ORDER:
                    target["counts"][category][cargo] = int((by_cat["cargo_state"] == cargo).sum())
        return result

    def filtered_rows(snapshot: dict, idle_bucket: Optional[str], kind: Optional[str], cargo: Optional[str], wagon_number: Optional[str] = None) -> list[dict]:
        rows = list(snapshot.get("rows", []))
        out: list[dict] = []
        normalized_wagon = normalize_wagon_number(wagon_number or "")
        for item in rows:
            if idle_bucket and item.get("idle_bucket") != idle_bucket:
                continue
            if kind and kind != "Всего" and item.get("kind_group") != kind:
                continue
            if cargo in CARGO_ORDER and item.get("cargo_state") != cargo:
                continue
            if normalized_wagon and normalize_wagon_number(item.get("wagon_number", "")) != normalized_wagon:
                continue
            out.append(item)
        return out

    def metric_cards(snapshot: dict) -> list[dict]:
        rows = snapshot.get("rows", []) if isinstance(snapshot, dict) else []
        total = len(rows)
        danger = sum(1 for item in rows if item.get("idle_bucket") == "30plus")
        commented = sum(1 for item in rows if str(item.get("comment_text", "") or "").strip())
        return [
            {"label": "Всего", "count": total, "sub": "Актуальные вагоны во вкладке", "danger": False},
            {"label": "30 суток и более", "count": danger, "sub": "Контроль длительного простоя", "danger": True},
            {"label": "С комментариями", "count": commented, "sub": "Непустые примечания", "danger": False},
        ]

    def build_filter_caption(idle_bucket: Optional[str], kind: Optional[str], cargo: Optional[str]) -> str:
        parts = []
        if idle_bucket:
            parts.append(next((label for key, label in STATION_IDLE_BUCKETS if key == idle_bucket), idle_bucket))
        if kind:
            parts.append(kind)
        if cargo == "гр":
            parts.append("Гружёные")
        elif cargo == "пор":
            parts.append("Порожние")
        return " / ".join(parts) if parts else f"Все вагоны из вкладки «Простой на станции {get_selected_station("Углеуральская")}»"

    def detail_link(idle_bucket: Optional[str], kind: str, cargo: str, archive_date: Optional[str]) -> Optional[str]:
        params = {}
        if idle_bucket:
            params["idle_bucket"] = idle_bucket
        if kind and kind != "Всего":
            params["kind"] = kind
        if cargo in CARGO_ORDER:
            params["cargo"] = cargo
        if archive_date:
            params["archive_date"] = archive_date
        payload = {key: value for key, value in params.items() if value}
        return url_for("idle_comments_details") + (("?" + urlencode(payload)) if payload else "")

    @app.route("/idle-comments")
    def idle_comments_index():
        archive_date = str(request.args.get("archive_date") or "").strip()
        if archive_date:
            snapshot = load_snapshot(archive_date)
            if snapshot is None:
                set_error("Архив комментариев за выбранную дату отсутствует.")
                return redirect(url_for("idle_comments_index"))
        else:
            snapshot = build_current_snapshot()
        rows = summary_rows_from_snapshot(snapshot)
        for row in rows:
            row["links"] = {
                category: {cargo: detail_link(row.get("idle_bucket"), category, cargo, archive_date or None) for cargo in CARGO_ORDER}
                for category in STATION_IDLE_UGL_CATEGORY_ORDER
            }
        return render_page(
            IDLE_COMMENTS_INDEX_BODY,
            title=f"{APP_TITLE} — простой с комментариями",
            app_title=APP_TITLE,
            rows=rows,
            category_order=STATION_IDLE_UGL_CATEGORY_ORDER,
            cargo_order=CARGO_ORDER,
            archive_date=archive_date,
            metric_cards=metric_cards(snapshot),
            source_name=snapshot.get("source_name", "Файл ещё не загружен"),
            source_time=snapshot.get("source_time", ""),
            report_date_label=snapshot.get("report_dt_label", snapshot.get("report_date", "")),
            success_message=pop_success(),
            error_message=pop_error(),
            search_wagon=request.args.get("search_wagon", ""),
            search_date_from=request.args.get("search_date_from", ""),
            search_date_to=request.args.get("search_date_to", ""),
            selected_station=get_selected_station("Углеуральская"),
        )

    @app.route("/idle-comments/details")
    def idle_comments_details():
        archive_date = str(request.args.get("archive_date") or "").strip()
        idle_bucket = str(request.args.get("idle_bucket") or "").strip() or None
        kind = str(request.args.get("kind") or "").strip() or None
        cargo = str(request.args.get("cargo") or "").strip() or None
        wagon_number = normalize_wagon_number(request.args.get("wagon", ""))
        snapshot = load_snapshot(archive_date) if archive_date else build_current_snapshot()
        if snapshot is None:
            set_error("Архив комментариев за выбранную дату отсутствует.")
            return redirect(url_for("idle_comments_index"))
        records = filtered_rows(snapshot, idle_bucket, kind, cargo, wagon_number or None)
        caption = build_filter_caption(idle_bucket, kind, cargo)
        if wagon_number:
            caption = f"Поиск вагона {wagon_number}" + (f" / {caption}" if caption else "")
        return render_idle_comments_detail(
            records=records,
            filter_caption=caption,
            archive_mode=bool(archive_date),
            archive_date=archive_date,
            idle_bucket=idle_bucket,
            kind=kind,
            cargo=cargo,
            search_wagon=wagon_number,
            export_archive_date=archive_date,
        )

    @app.route("/idle-comments/search")
    def idle_comments_search():
        wagon_number = normalize_wagon_number(request.args.get("wagon", ""))
        date_from_raw = str(request.args.get("date_from") or "").strip()
        date_to_raw = str(request.args.get("date_to") or "").strip()
        if not wagon_number:
            set_error("Введите номер вагона.")
            return redirect(url_for("idle_comments_index", search_wagon=request.args.get("wagon", ""), search_date_from=date_from_raw, search_date_to=date_to_raw))

        date_from = parse_snapshot_date(date_from_raw)
        date_to = parse_snapshot_date(date_to_raw)
        if date_from_raw and date_from is None:
            set_error("Неверно указана дата начала периода.")
            return redirect(url_for("idle_comments_index", search_wagon=wagon_number, search_date_from=date_from_raw, search_date_to=date_to_raw))
        if date_to_raw and date_to is None:
            set_error("Неверно указана дата окончания периода.")
            return redirect(url_for("idle_comments_index", search_wagon=wagon_number, search_date_from=date_from_raw, search_date_to=date_to_raw))
        if date_from and date_to and date_from > date_to:
            set_error("Неверно указан период поиска.")
            return redirect(url_for("idle_comments_index", search_wagon=wagon_number, search_date_from=date_from_raw, search_date_to=date_to_raw))

        if not date_from and not date_to:
            snapshot = build_current_snapshot()
            records = filtered_rows(snapshot, None, None, None, wagon_number)
            if not records:
                set_error("Вагон в текущей дислокации не найден.")
                return redirect(url_for("idle_comments_index", search_wagon=wagon_number))
            return redirect(url_for("idle_comments_details", wagon=wagon_number))

        matched: list[dict] = []
        for report_date_obj, report_key in available_snapshot_dates(date_from, date_to):
            snapshot = load_snapshot(report_key)
            if not snapshot:
                continue
            for item in filtered_rows(snapshot, None, None, None, wagon_number):
                row = dict(item)
                row["report_date_display"] = report_date_obj.strftime("%d.%m.%Y")
                row["report_date_key"] = report_key
                matched.append(row)
        if not matched:
            set_error("Вагон в архиве за выбранный период не найден.")
            return redirect(url_for("idle_comments_index", search_wagon=wagon_number, search_date_from=date_from_raw, search_date_to=date_to_raw))
        caption = f"Поиск вагона {wagon_number} в архиве"
        if date_from_raw or date_to_raw:
            if date_from_raw and date_to_raw:
                caption += f" / период {date_from_raw} — {date_to_raw}"
            elif date_from_raw:
                caption += f" / с {date_from_raw}"
            else:
                caption += f" / по {date_to_raw}"
        archive_label = matched[0].get("report_date_display", "") if len(matched) == 1 else f"{len(matched)} совпадений"
        return render_idle_comments_detail(
            records=matched,
            filter_caption=caption,
            archive_mode=True,
            archive_date=archive_label,
            show_report_date=True,
            search_wagon=wagon_number,
            search_date_from=date_from_raw,
            search_date_to=date_to_raw,
            back_url=url_for("idle_comments_index", search_wagon=wagon_number, search_date_from=date_from_raw, search_date_to=date_to_raw),
            export_archive_date="",
        )

    @app.route("/idle-comments/save", methods=["POST"])
    def idle_comments_save():
        idle_bucket = str(request.form.get("idle_bucket") or "").strip() or None
        kind = str(request.form.get("kind") or "").strip() or None
        cargo = str(request.form.get("cargo") or "").strip() or None
        snapshot = build_current_snapshot()
        rows = filtered_rows(snapshot, idle_bucket, kind, cargo)
        wagons = request.form.getlist("wagon_number")
        comments = request.form.getlist("comment_text")
        current_comments = load_current_comments()
        row_map = {item["wagon_number"]: item for item in snapshot.get("rows", [])}
        changed = 0
        ts = now_func().strftime("%d.%m.%Y %H:%M:%S")
        for wagon, comment in zip(wagons, comments):
            wagon_key = normalize_wagon_number(wagon)
            row_item = row_map.get(wagon_key, {})
            arrived_at_iso = str(row_item.get("arrived_at_iso", "") or "")
            text = str(comment or "").strip()
            prev_text, prev_updated_at = get_shared_comment(current_comments, wagon_key, arrived_at_iso)
            updated_at = prev_updated_at
            if text != prev_text:
                updated_at = ts if text else ""
                changed += 1
            current_comments = set_shared_comment(current_comments, wagon_key, arrived_at_iso, text, updated_at)
            if wagon_key in row_map:
                row_map[wagon_key]["comment_text"] = text
                row_map[wagon_key]["comment_updated_at"] = updated_at
        save_current_comments(current_comments)
        save_snapshot(snapshot)
        set_success(f"Изменения сохранены: {changed} строк.")
        return redirect(url_for("idle_comments_details", idle_bucket=idle_bucket, kind=kind, cargo=cargo))



    @app.route("/idle-comments/export", methods=["POST"])
    def idle_comments_export():
        payload_raw = str(request.form.get("filtered_rows") or "").strip()
        idle_bucket = str(request.form.get("idle_bucket") or "").strip() or None
        kind = str(request.form.get("kind") or "").strip() or None
        cargo = str(request.form.get("cargo") or "").strip() or None
        archive_date = str(request.form.get("archive_date") or "").strip() or None
        rows: list[dict] = []
        if payload_raw:
            try:
                payload = json.loads(payload_raw)
                if isinstance(payload, list):
                    rows = [item for item in payload if isinstance(item, dict)]
            except Exception:
                rows = []
        if not rows:
            snapshot = load_snapshot(archive_date) if archive_date else build_current_snapshot()
            if snapshot is None:
                set_error("Архив комментариев за выбранную дату отсутствует.")
                return redirect(url_for("idle_comments_index"))
            rows = filtered_rows(snapshot, idle_bucket, kind, cargo)
        export_df = detail_export_frame(rows)
        current_state = get_approach_state()
        if archive_date:
            suffix = archive_date
        elif current_state is not None:
            suffix = current_report_date_key(current_state)
        else:
            suffix = now_func().strftime("%Y-%m-%d")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            temp_path = tmp.name
        write_single_sheet_excel(export_df, temp_path, sheet_name="Простой с комментариями")
        download_name = f"idle_comments_detail_{suffix}.xlsx"
        return send_file(temp_path, as_attachment=True, download_name=download_name, max_age=0)

    @app.route("/idle-comments/reasons")
    def idle_comments_reasons():
        return render_page(
            IDLE_COMMENTS_REASONS_BODY,
            title=f"{APP_TITLE} — причины простоя",
            reasons=load_reasons(),
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/idle-comments/reasons/add", methods=["POST"])
    def idle_comments_reasons_add():
        reason = str(request.form.get("reason") or "").strip()
        reasons = load_reasons()
        if reason and reason.casefold() not in {item.casefold() for item in reasons}:
            reasons.append(reason)
            save_reasons(reasons)
            set_success("Причина добавлена.")
        return redirect(url_for("idle_comments_reasons"))

    @app.route("/idle-comments/reasons/update", methods=["POST"])
    def idle_comments_reasons_update():
        old_reason = str(request.form.get("old_reason") or "").strip()
        new_reason = str(request.form.get("new_reason") or "").strip()
        reasons = load_reasons()
        updated = []
        seen = set()
        for item in reasons:
            value = new_reason if item == old_reason and new_reason else item
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            updated.append(value)
        save_reasons(updated)
        set_success("Причина обновлена.")
        return redirect(url_for("idle_comments_reasons"))

    @app.route("/idle-comments/reasons/delete", methods=["POST"])
    def idle_comments_reasons_delete():
        reason = str(request.form.get("reason") or "").strip()
        reasons = [item for item in load_reasons() if item != reason]
        save_reasons(reasons)
        set_success("Причина удалена.")
        return redirect(url_for("idle_comments_reasons"))
