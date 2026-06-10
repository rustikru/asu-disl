from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import pandas as pd
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import Flask, jsonify, redirect, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from core import (
    CARGO_ORDER,
    CATEGORY_ORDER,
    DESTINATION_KEYWORD,
    STATION_IDLE_BUCKETS,
    STATION_IDLE_CATEGORY_ORDER,
    STATION_IDLE_UGL_CATEGORY_ORDER,
    build_station_idle_frame,
    build_station_idle_rows,
    build_summary_frame,
    build_summary_rows,
    build_train_presentation_rows,
    count_formed_trains,
    count_train_card_wagons,
    filter_detail,
    filter_primary_destination,
    is_stop_rent_end_operation,
    load_excel_as_df,
    normalize_wagon_number,
    parse_report_datetime,
    strip_last_numeric_code,
    whole_calendar_days,
    build_raw_material_idle_frame,
    build_raw_material_idle_rows,
    filter_raw_material_idle,
    raw_material_idle_label,
)
from core.dataframe_ops import (
    _extract_exact_wagon_values,
    build_station_destination_idle_frame,
    build_station_destination_idle_rows,
    filter_station_destination_idle,
    filter_station_idle_destination,
)
from core.parsers import parse_any_date, parse_any_datetime, parse_distance_km
from core.normalization import normalize_spaces
from core.rules import same_station_name
from core.raw_material_idle import RAW_MATERIAL_IDLE_LIMIT_DAYS, RAW_MATERIAL_IDLE_OVERFLOW_FILTER
from .config import (
    APP_TITLE,
    APPROACH_ORIGIN_CARDS,
    ARCHIVE_METADATA_FILE,
    DEPARTURE_DESTINATION_CARDS,
    STOP_RENT_FILE,
    STOP_RENT_SECURITY_FILE,
    TAB_APPROACH,
    TAB_DEPARTURE,
    TAB_LABELS,
    TAB_LOADING,
    TAB_RAW_MATERIAL,
    TAB_MAILING,
    TAB_MANUAL,
    TAB_STATION_IDLE,
    TAB_ARCHIVE,
    get_user_data_dir,
    get_user_data_file,
    get_user_data_subdir,
    MAILING_DB_FILE,
    MAILING_POLL_INTERVAL_SECONDS,
    MANUAL_FILTERS_FILE,
    STATION_DIRECTORY_FILE,
)
from .export_service import detail_export_frame, manual_filter_export_frame, write_excel_report, write_single_sheet_excel
from .license_service import (
    build_activation_request_filename,
    build_activation_request_payload,
    get_license_state,
    get_update_info,
    install_license_file,
    load_license_settings,
    remove_local_license,
)
from .mail_service import fetch_latest_excel_from_mail, fetch_latest_excel_from_folder, get_imap_config, load_settings, remove_previous_mail_files
from .models import MailFetchResult, SourceState
from .mailing_models import MailingRule, MailingScheduleType
from .mailing_reports import ReportBuilderRegistry
from .mailing_scheduler import MailingScheduler, describe_schedule
from .mailing_service import OutlookMailSender
from .mailing_storage import MailingStorage
from .loading_month_service import build_day_records, build_loading_month_report, normalize_month_key
from .loading_month_templates import LOADING_MONTH_BODY
from .archive_service import archive_export_frame, archive_files_status, parse_archive_wagon_numbers, search_archive_records
from .archive_templates import ARCHIVE_BODY
from .idle_comments_service import register_idle_comments_routes
from .technical_state_service import register_technical_state_routes
from .claims_ugleuralskaya_service import register_claims_ugleuralskaya_routes
from .templates import (
    ACTIVATION_BODY,
    DETAIL_BODY,
    INDEX_BODY,
    MANUAL_FILTER_BODY,
    STOP_RENT_ACCESS_BODY,
    STOP_RENT_BODY,
    STOP_RENT_PASSWORD_BODY,
    MAILING_BODY,
    MAILING_FORM_BODY,
    MAILING_LOGS_BODY,
    MAP_BODY,
    DASHBOARD_BODY,
    SETTINGS_BODY,
    STATION_SELECT_BODY,
)
from .utils import best_lan_ip, render_page
from core.station_context import (
    clear_selected_station,
    normalize_station_key,
    normalize_station_name,
    set_selected_station,
    station_matches,
)

TAB_DASHBOARD = "dashboard"
TAB_STATION_SELECT = "station_select"
TAB_SETTINGS = "settings"
EXTRA_TAB_LABELS = {
    TAB_DASHBOARD: "Главный экран",
    TAB_STATION_SELECT: "Выбрать станцию",
    TAB_SETTINGS: "Настройки",
}


def create_app(default_excel: Optional[str] = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("ASU_PODHOD_SECRET") or f"asu-podhod-{APP_TITLE}-secret"
    app.config["CURRENT_STATES"] = {TAB_APPROACH: None, TAB_DEPARTURE: None}
    app.config["DEFAULT_EXCEL"] = default_excel
    app.config["LAST_ERROR"] = None
    app.config["LAST_SUCCESS"] = None

    base_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    settings = load_settings(base_dir)
    app.config["SETTINGS"] = settings
    license_settings = load_license_settings(base_dir)
    # Disable license requirement for development
    license_settings["enabled"] = False
    license_settings["require_license"] = False
    app.config["LICENSE_SETTINGS"] = license_settings
    app.config["BASE_DIR"] = base_dir

    host_env = os.environ.get("HOST", "127.0.0.1")
    port_env = int(os.environ.get("PORT", "8510"))
    app.config["LOCAL_URL"] = f"http://127.0.0.1:{port_env}"
    app.config["LAN_URL"] = f"http://{best_lan_ip()}:{port_env}"
    app.config["HOST_MODE"] = host_env

    data_root = get_user_data_dir()
    upload_dir = get_user_data_subdir("uploads")
    mail_dir = get_user_data_subdir("mail")
    export_dir = get_user_data_subdir("exports")
    archive_dir = get_user_data_subdir("archive")
    archive_meta_path = data_root / ARCHIVE_METADATA_FILE
    stop_rent_path = data_root / STOP_RENT_FILE
    stop_rent_security_path = data_root / STOP_RENT_SECURITY_FILE
    mailing_db_path = get_user_data_file(MAILING_DB_FILE)
    manual_filters_path = get_user_data_file(MANUAL_FILTERS_FILE)
    notification_rules_path = get_user_data_file("notification_rules.json")
    notification_channel_path = get_user_data_file("notification_channel.json")
    ui_preferences_path = get_user_data_file("ui_preferences.json")
    selected_station_path = get_user_data_file("selected_station.json")
    station_sources_path = get_user_data_file("station_sources.json")
    export_preferences_path = get_user_data_file("export_preferences.json")
    mailing_storage = MailingStorage(mailing_db_path)
    mailing_registry = ReportBuilderRegistry()
    mailing_sender = OutlookMailSender()
    mail_sync_lock = threading.RLock()

    STOP_RENT_DEFAULT_PASSWORD = "1234"
    stop_rent_reset_public_key_path = base_dir / "stop_rent_reset_public.pem"

    MOSCOW_TZ = timezone(timedelta(hours=3))

    def now() -> datetime:
        return datetime.now()

    def moscow_today() -> date:
        return datetime.now(MOSCOW_TZ).date()

    def _hex_to_rgba(value: str, alpha: float) -> str:
        raw = str(value or '').strip().lstrip('#')
        if len(raw) == 3:
            raw = ''.join(ch * 2 for ch in raw)
        if len(raw) != 6:
            raw = '2456d4'
        try:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
        except Exception:
            r, g, b = (36, 86, 212)
        alpha = max(0.0, min(1.0, float(alpha)))
        return f"rgba({r}, {g}, {b}, {alpha:.3f})"


    def get_approach_state() -> Optional[SourceState]:
        set_current_station_context()
        state = ensure_loaded(TAB_APPROACH)
        if not get_selected_station_name():
            return _empty_state_like(state, TAB_APPROACH)
        return _prepare_state_for_selected_station(TAB_APPROACH, state)

    def get_departure_state() -> Optional[SourceState]:
        set_current_station_context()
        state = ensure_loaded(TAB_DEPARTURE)
        if not get_selected_station_name():
            return _empty_state_like(state, TAB_DEPARTURE)
        return _prepare_state_for_selected_station(TAB_DEPARTURE, state)

    def is_safe_next_url(value: Optional[str]) -> bool:
        return bool(value) and str(value).startswith("/") and not str(value).startswith("//")

    def get_idle_view(raw_value: Optional[str]) -> str:
        return "destination" if str(raw_value or "").strip() == "destination" else "ugleuralskaya"

    def get_loading_view(raw_value: Optional[str]) -> str:
        value = str(raw_value or "").strip()
        if value == "pending":
            return "pending"
        if value == "month":
            return "month"
        if value == "yesterday":
            return "yesterday"
        return "today"

    def _norm_filter_text(value: object) -> str:
        return normalize_spaces(value).upper().replace("Ё", "Е")

    def _first_existing_series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
        for column in candidates:
            if column in df.columns:
                return df[column].fillna("").astype(str)
        return pd.Series("", index=df.index)

    def _unique_filter_options(df: pd.DataFrame, candidates: list[str]) -> list[str]:
        if df is None or df.empty:
            return []
        series = _first_existing_series(df, candidates).map(normalize_spaces)
        values = [value for value in series.dropna().unique().tolist() if normalize_spaces(value)]
        return sorted(values, key=lambda value: value.upper().replace("Ё", "Е"))


    DEFAULT_WORK_STATION = "Углеуральская"

    def _load_selected_station_raw() -> str:
        payload = load_json_file(selected_station_path, {})
        if not isinstance(payload, dict):
            return ""
        return normalize_station_name(payload.get("station") or "")

    def get_selected_station_name() -> str:
        return _load_selected_station_raw()

    def has_selected_station() -> bool:
        return bool(get_selected_station_name())

    def set_current_station_context() -> str:
        station = get_selected_station_name()
        if station:
            set_selected_station(station)
        else:
            clear_selected_station()
        return station

    def save_selected_station(value: object) -> str:
        station = normalize_station_name(value)
        if not station:
            raise ValueError("Не указана станция.")
        allowed_options = {normalize_station_key(item) for item in get_station_options()}
        if normalize_station_key(station) not in allowed_options:
            raise ValueError("Станция не добавлена в настройках.")
        previous_station = get_selected_station_name()
        save_json_file(selected_station_path, {
            "station": station,
            "station_key": normalize_station_key(station),
            "selected_at": now().isoformat(),
        })
        set_selected_station(station)
        if normalize_station_key(previous_station) != normalize_station_key(station):
            set_state(TAB_APPROACH, None)
            set_state(TAB_DEPARTURE, None)
        return station

    def clear_selected_station_file() -> None:
        try:
            selected_station_path.unlink(missing_ok=True)
        except Exception:
            save_json_file(selected_station_path, {})
        clear_selected_station()

    def _station_matches_selected(value: object, station: Optional[str] = None) -> bool:
        target = station or get_selected_station_name() or DEFAULT_WORK_STATION
        return station_matches(value, target)

    def _station_slug(value: object) -> str:
        station = normalize_station_name(value)
        key = normalize_station_key(station)
        slug = re.sub(r"[^A-ZА-Я0-9]+", "_", key).strip("_").lower()
        if not slug:
            slug = hashlib.sha1(station.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return slug

    def is_base_station(value: object) -> bool:
        return normalize_station_key(value) == normalize_station_key(DEFAULT_WORK_STATION)

    def _normalize_direction_name(value: object) -> str:
        return normalize_spaces(value)

    def _unique_direction_names(values: object) -> list[str]:
        if values is None:
            return []
        if isinstance(values, str):
            raw_items = re.split(r"[\n,;]+", values)
        elif isinstance(values, (list, tuple, set)):
            raw_items = list(values)
        else:
            raw_items = [values]
        result: list[str] = []
        seen: set[str] = set()
        for raw in raw_items:
            name = _normalize_direction_name(raw)
            key = normalize_station_key(name)
            if not name or not key or key in seen:
                continue
            seen.add(key)
            result.append(name)
        return result

    def _default_station_directions() -> dict:
        return {
            "approach": [{"name": name, "enabled": True} for name in APPROACH_ORIGIN_CARDS],
            "departure": [{"name": name, "enabled": True} for name in DEPARTURE_DESTINATION_CARDS],
        }

    def _normalize_direction_items(raw_items: object, default_names: list[str]) -> list[dict]:
        if not isinstance(raw_items, list):
            raw_items = []
        result: list[dict] = []
        seen: set[str] = set()

        def add_item(name: object, enabled: object = True) -> None:
            normalized = _normalize_direction_name(name)
            key = normalize_station_key(normalized)
            if not normalized or not key or key in seen:
                return
            seen.add(key)
            result.append({"name": normalized, "enabled": bool(enabled)})

        for item in raw_items:
            if isinstance(item, dict):
                add_item(item.get("name"), item.get("enabled", True))
            else:
                add_item(item, True)
        if not result:
            for name in default_names:
                add_item(name, True)
        return result

    def _normalize_station_directions(raw: object) -> dict:
        raw = raw if isinstance(raw, dict) else {}
        return {
            "approach": _normalize_direction_items(raw.get("approach"), list(APPROACH_ORIGIN_CARDS)),
            "departure": _normalize_direction_items(raw.get("departure"), list(DEPARTURE_DESTINATION_CARDS)),
        }

    def _build_direction_config_from_form(source_key: str) -> list[dict]:
        default_names = list(APPROACH_ORIGIN_CARDS if source_key == "approach" else DEPARTURE_DESTINATION_CARDS)
        enabled_standard = {normalize_station_key(item) for item in request.form.getlist(f"{source_key}_direction_enabled")}
        custom_names = _unique_direction_names(request.form.get(f"{source_key}_custom_directions"))
        result: list[dict] = []
        seen: set[str] = set()

        def add_item(name: str, enabled: bool) -> None:
            normalized = _normalize_direction_name(name)
            key = normalize_station_key(normalized)
            if not normalized or not key or key in seen:
                return
            seen.add(key)
            result.append({"name": normalized, "enabled": bool(enabled)})

        for name in default_names:
            add_item(name, normalize_station_key(name) in enabled_standard)
        for name in custom_names:
            add_item(name, True)
        return result

    def _direction_names_for_station(source_key: str, station: Optional[object] = None) -> list[str]:
        default_names = list(APPROACH_ORIGIN_CARDS if source_key == "approach" else DEPARTURE_DESTINATION_CARDS)
        station_name = normalize_station_name(station if station is not None else get_selected_station_name())
        if not station_name or is_base_station(station_name):
            return default_names
        cfg = get_station_source_config(station_name)
        if not cfg:
            return []
        directions = _normalize_station_directions(cfg.get("directions"))
        result = [item.get("name") for item in directions.get(source_key, []) if bool(item.get("enabled", True)) and normalize_spaces(item.get("name"))]
        return _unique_direction_names(result)

    def get_approach_direction_cards() -> list[str]:
        return _direction_names_for_station("approach")

    def get_departure_direction_cards() -> list[str]:
        return _direction_names_for_station("departure")

    def _is_approach_direction(value: object) -> bool:
        key = normalize_station_key(value)
        return bool(key) and key in {normalize_station_key(item) for item in get_approach_direction_cards()}

    def _is_departure_direction(value: object) -> bool:
        key = normalize_station_key(value)
        return bool(key) and key in {normalize_station_key(item) for item in get_departure_direction_cards()}

    def _blank_station_source_config(station_name: str = "") -> dict:
        return {
            "id": uuid.uuid4().hex,
            "name": normalize_station_name(station_name),
            "station_key": normalize_station_key(station_name),
            "slug": _station_slug(station_name),
            "enabled": True,
            "approach": {
                "mailbox": "",
                "subject_filter": "",
                "subject_equals": "",
                "attachment_name_contains": "",
                "attachment_name_equals": "",
            },
            "departure": {
                "mailbox": "",
                "subject_filter": "",
                "subject_equals": "",
                "attachment_name_contains": "",
                "attachment_name_equals": "",
            },
            "directions": _default_station_directions(),
            "created_at": now().isoformat(),
            "updated_at": now().isoformat(),
        }

    def load_station_sources() -> list[dict]:
        payload = load_json_file(station_sources_path, {})
        raw_items = payload.get("stations") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []
        result: list[dict] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            name = normalize_station_name(raw.get("name"))
            key = normalize_station_key(name)
            if not name or not key or is_base_station(name) or key in seen:
                continue
            item = _blank_station_source_config(name)
            item.update({k: v for k, v in raw.items() if k not in {"approach", "departure", "directions"}})
            item["name"] = name
            item["station_key"] = key
            item["slug"] = _station_slug(name)
            item["enabled"] = bool(raw.get("enabled", True))
            for source_key in ("approach", "departure"):
                current = item.get(source_key) if isinstance(item.get(source_key), dict) else {}
                incoming = raw.get(source_key) if isinstance(raw.get(source_key), dict) else {}
                current.update({
                    "mailbox": normalize_spaces(incoming.get("mailbox")),
                    "subject_filter": normalize_spaces(incoming.get("subject_filter")),
                    "subject_equals": normalize_spaces(incoming.get("subject_equals")),
                    "attachment_name_contains": normalize_spaces(incoming.get("attachment_name_contains")),
                    "attachment_name_equals": normalize_spaces(incoming.get("attachment_name_equals")),
                })
                item[source_key] = current
            item["directions"] = _normalize_station_directions(raw.get("directions"))
            seen.add(key)
            result.append(item)
        return sorted(result, key=lambda x: normalize_station_key(x.get("name")))

    def save_station_sources(items: list[dict]) -> None:
        cleaned: list[dict] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            name = normalize_station_name(item.get("name"))
            key = normalize_station_key(name)
            if not name or not key or is_base_station(name) or key in seen:
                continue
            item = dict(item)
            item["name"] = name
            item["station_key"] = key
            item["slug"] = _station_slug(name)
            item["enabled"] = bool(item.get("enabled", True))
            item["directions"] = _normalize_station_directions(item.get("directions"))
            item["updated_at"] = now().isoformat()
            cleaned.append(item)
            seen.add(key)
        save_json_file(station_sources_path, {"stations": cleaned})

    def get_station_source_config(station: Optional[object] = None) -> Optional[dict]:
        station_name = normalize_station_name(station if station is not None else get_selected_station_name())
        if not station_name or is_base_station(station_name):
            return None
        key = normalize_station_key(station_name)
        for item in load_station_sources():
            if bool(item.get("enabled", True)) and normalize_station_key(item.get("name")) == key:
                return item
        return None

    def get_station_options() -> list[str]:
        items: list[str] = [DEFAULT_WORK_STATION]
        items.extend([str(item.get("name") or "") for item in load_station_sources() if bool(item.get("enabled", True))])
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            station = normalize_station_name(item)
            key = normalize_station_key(station)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(station)
        return result

    def _station_mail_dir(station: Optional[object] = None) -> Path:
        station_name = normalize_station_name(station if station is not None else get_selected_station_name())
        cfg = get_station_source_config(station_name)
        if not station_name or is_base_station(station_name):
            return mail_dir
        target = mail_dir / "stations" / str((cfg or {}).get("slug") or _station_slug(station_name))
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _source_key_for_tab(tab: str) -> str:
        return "approach" if tab == TAB_APPROACH else "departure"

    def _effective_mail_settings_for_tab(tab: str) -> dict:
        settings_payload = app.config.get("SETTINGS", {})
        selected_station = get_selected_station_name()
        cfg = get_station_source_config()
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return settings_payload
        if not cfg:
            if selected_station and not is_base_station(selected_station):
                imap_key = "imap_approach" if tab == TAB_APPROACH else "imap_departure"
                base_common = dict(settings_payload.get("imap", {})) if isinstance(settings_payload, dict) else {}
                disabled = dict(get_imap_config(settings_payload, tab))
                disabled["enabled"] = False
                merged = dict(settings_payload) if isinstance(settings_payload, dict) else {}
                merged["imap"] = base_common
                merged[imap_key] = disabled
                return merged
            return settings_payload
        source_key = _source_key_for_tab(tab)
        source_cfg = cfg.get(source_key) if isinstance(cfg.get(source_key), dict) else {}
        imap_key = "imap_approach" if tab == TAB_APPROACH else "imap_departure"
        base_common = dict(settings_payload.get("imap", {})) if isinstance(settings_payload, dict) else {}
        base_tab = dict(get_imap_config(settings_payload, tab))
        merged_tab = {**base_tab}
        for name in ["mailbox", "subject_filter", "subject_equals", "attachment_name_contains", "attachment_name_equals"]:
            value = normalize_spaces(source_cfg.get(name))
            if value:
                merged_tab[name] = value
        merged_tab["enabled"] = bool(normalize_spaces(source_cfg.get("mailbox")))
        merged = dict(settings_payload) if isinstance(settings_payload, dict) else {}
        merged["imap"] = base_common
        merged[imap_key] = merged_tab
        return merged

    def station_sources_warning_for_selected() -> str:
        station = get_selected_station_name()
        if not station or is_base_station(station):
            return ""
        cfg = get_station_source_config(station)
        if not cfg:
            return f"Для станции «{station}» не настроены источники справок. Откройте настройки и задайте Подход вагонов и Отправление вагонов."
        missing = []
        for source_key, label in [("approach", "Подход вагонов"), ("departure", "Отправление вагонов")]:
            source_cfg = cfg.get(source_key) if isinstance(cfg.get(source_key), dict) else {}
            if not normalize_spaces(source_cfg.get("mailbox")):
                missing.append(label)
        if missing:
            return f"Для станции «{station}» не настроены источники: {', '.join(missing)}."
        return ""

    def _station_bound_tab(tab: str) -> bool:
        return tab in {TAB_APPROACH, TAB_DEPARTURE, TAB_LOADING, TAB_STATION_IDLE, TAB_RAW_MATERIAL}

    def _prepare_state_for_selected_station(tab: str, state: Optional[SourceState]) -> Optional[SourceState]:
        if state is None or state.df is None:
            return state
        station = get_selected_station_name()
        if not station:
            return state
        df = state.df.copy()
        # approach/raw/station idle используют выбранную станцию как станцию назначения/операции.
        if "Станция назначения" in df.columns:
            df["primary_destination_match"] = df["Станция назначения"].map(lambda value: _station_matches_selected(value, station))
        # departure/loading используют выбранную станцию как станцию отправления.
        if tab in {TAB_DEPARTURE, TAB_LOADING} and "Станция отправления" in df.columns:
            df = df[df["Станция отправления"].map(lambda value: _station_matches_selected(value, station))].copy()
        return _state_with_df(state, df.reset_index(drop=True))

    def _empty_state_like(state: Optional[SourceState], mode: str) -> SourceState:
        if state is not None and isinstance(state.df, pd.DataFrame):
            empty_df = state.df.iloc[0:0].copy()
            return _state_with_df(state, empty_df)
        return SourceState(
            df=pd.DataFrame(),
            source_name="Станция не выбрана",
            loaded_at=now(),
            report_dt=now(),
            file_path=None,
            source_kind="station",
            mail_signature=None,
            mode=mode,
        )

    def _apply_approach_header_filters(
        df: pd.DataFrame,
        cargo_filter: Optional[str] = None,
        previous_cargo_filter: Optional[str] = None,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        out = df.copy()
        cargo_target = _norm_filter_text(cargo_filter)
        if cargo_target:
            cargo_mask = pd.Series(False, index=out.index)
            for column in ["cargo_name_display", "Наименование груза", "Груз"]:
                if column in out.columns:
                    cargo_mask = cargo_mask | (out[column].map(_norm_filter_text) == cargo_target)
            out = out[cargo_mask].copy()
        previous_target = _norm_filter_text(previous_cargo_filter)
        if previous_target:
            previous_mask = pd.Series(False, index=out.index)
            for column in ["previous_cargo_display", "Ранее выгруженный груз"]:
                if column in out.columns:
                    previous_mask = previous_mask | (out[column].map(_norm_filter_text) == previous_target)
            out = out[previous_mask].copy()
        return out

    def _state_with_df(state: SourceState, df: pd.DataFrame) -> SourceState:
        return SourceState(
            df=df,
            source_name=state.source_name,
            loaded_at=state.loaded_at,
            report_dt=state.report_dt,
            file_path=state.file_path,
            source_kind=state.source_kind,
            mail_signature=state.mail_signature,
            mode=state.mode,
        )

    def get_station_idle_source_tab(idle_view: str) -> str:
        return TAB_DEPARTURE if idle_view == "destination" else TAB_APPROACH

    def _dynamic_tab_label(tab: str, default_label: str) -> str:
        station = get_selected_station_name()
        if not station:
            return default_label
        if tab == TAB_STATION_IDLE:
            return "Простои"
        if tab == TAB_RAW_MATERIAL:
            return "Сырье"
        return default_label.replace("Углеуральская", station).replace("Углеуральской", station)

    def get_detail_section_label(tab: str, idle_view: str, loading_view: str) -> str:
        if tab == TAB_STATION_IDLE:
            return "Простой на станции назначения" if idle_view == "destination" else f"Простой на станции {get_selected_station_name() or DEFAULT_WORK_STATION}"
        if tab == TAB_LOADING:
            if loading_view == "pending":
                return "Погружены, но не отправлены"
            if loading_view == "month":
                return "Погрузка с начала месяца"
            if loading_view == "yesterday":
                return "Погрузка вчера"
            return "Погрузка сегодня"
        return TAB_LABELS.get(tab, tab)

    def sanitize_download_label(value: object) -> str:
        text_value = normalize_spaces(value)
        text_value = re.sub(r'[<>:"/\\|?*]+', '_', text_value)
        text_value = re.sub(r'\s+', '_', text_value)
        text_value = re.sub(r'_+', '_', text_value).strip('._ ')
        return text_value or 'report'

    def build_detail_download_name(tab: str, idle_view: str, loading_view: str, *, raw: bool = False) -> str:
        section_label = sanitize_download_label(get_detail_section_label(tab, idle_view, loading_view))
        stamp = now().strftime('%Y%m%d_%H%M%S')
        if raw:
            return f"asu_podhod_{section_label}_исходные_{stamp}.xlsx"
        return f"asu_podhod_{section_label}_{stamp}.xlsx"

    def build_wagon_search_summary(exact_wagon: Optional[str], records: list[dict]) -> Optional[dict]:
        requested_wagons = _extract_exact_wagon_values(exact_wagon)
        if len(requested_wagons) <= 1:
            return None
        found_wagons: list[str] = []
        seen_found: set[str] = set()
        for record in records:
            wagon_number = normalize_wagon_number(record.get('wagon_number', ''))
            if re.fullmatch(r'\d{8}', wagon_number) and wagon_number not in seen_found:
                seen_found.add(wagon_number)
                found_wagons.append(wagon_number)
        missing_wagons = [wagon_number for wagon_number in requested_wagons if wagon_number not in seen_found]
        return {
            'requested_count': len(requested_wagons),
            'found_count': len(found_wagons),
            'missing_wagons': missing_wagons,
        }

    def _station_text(value: object) -> str:
        return str(value or "").strip().upper().replace("Ё", "Е")

    def is_ugleuralskaya_station(value: object) -> bool:
        # Историческое имя функции сохранено для совместимости,
        # но фактически она проверяет совпадение с текущей выбранной станцией.
        station = get_selected_station_name() or DEFAULT_WORK_STATION
        return station_matches(value, station)

    def _departure_from_acceptance_display(row: pd.Series) -> str:
        departure_value = row.get("Дата и время отправления со станции приема", "")
        if not normalize_spaces(departure_value):
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
        return str(departure_value) if departure_dt >= trip_start_dt else ""

    def _with_departure_acceptance_display(frame: pd.DataFrame) -> pd.DataFrame:
        """Добавляет служебную колонку с датой отправления со станции приёма.

        Карточки «Отправлено сегодня/вчера» считают дату через
        _departure_from_acceptance_display(), поэтому детализация должна
        фильтровать ровно тот же набор строк, а не искать только сырые
        варианты названия колонки.
        """
        if frame is None or not isinstance(frame, pd.DataFrame):
            return pd.DataFrame()
        helper_column = "__departure_acceptance_display"
        if helper_column in frame.columns:
            return frame
        out = frame.copy()
        if out.empty:
            out[helper_column] = pd.Series(dtype=object)
        else:
            out[helper_column] = out.apply(_departure_from_acceptance_display, axis=1)
        return out

    def filter_loading_view(frame: pd.DataFrame, report_dt: Optional[datetime], loading_view: str) -> pd.DataFrame:
        if frame is None or frame.empty or report_dt is None:
            return frame.iloc[0:0].copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()

        out = frame.copy()
        if "Станция отправления" not in out.columns:
            return out.iloc[0:0].copy()

        out = out[out["Станция отправления"].map(is_ugleuralskaya_station)].copy()
        if out.empty:
            return out.reset_index(drop=True)

        trip_col = "Дата и время начала рейса" if "Дата и время начала рейса" in out.columns else ("trip_start_time" if "trip_start_time" in out.columns else None)
        if trip_col is None:
            return out.iloc[0:0].copy()

        trip_dates = out[trip_col].map(parse_any_date)
        out = out[trip_dates.notna()].copy()
        if out.empty:
            return out.reset_index(drop=True)

        out["_loading_trip_date"] = trip_dates.loc[out.index]
        report_date = report_dt.date()
        yesterday_date = moscow_today() - timedelta(days=1)

        if loading_view == "pending":
            if "Станция операции" in out.columns:
                out = out[out["Станция операции"].map(is_ugleuralskaya_station)].copy()
            if out.empty:
                return out.reset_index(drop=True)
            out = out[out["_loading_trip_date"] != report_date].copy()
            if out.empty:
                return out.reset_index(drop=True)
            out = out[
                ~out.apply(lambda row: bool(normalize_spaces(_departure_from_acceptance_display(row))), axis=1)
            ].copy()
        elif loading_view == "yesterday":
            out = out[out["_loading_trip_date"] == yesterday_date].copy()
        else:
            out = out[out["_loading_trip_date"] == report_date].copy()

        return out.reset_index(drop=True)

    def filter_loading_month_frame(frame: pd.DataFrame, month_key: str) -> pd.DataFrame:
        if frame is None or frame.empty:
            return frame.iloc[0:0].copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()

        out = frame.copy()
        if "Станция отправления" not in out.columns:
            return out.iloc[0:0].copy()

        out = out[out["Станция отправления"].map(is_ugleuralskaya_station)].copy()
        if out.empty:
            return out.reset_index(drop=True)

        trip_col = "Дата и время начала рейса" if "Дата и время начала рейса" in out.columns else ("trip_start_time" if "trip_start_time" in out.columns else None)
        if trip_col is None:
            return out.iloc[0:0].copy()

        trip_dates = out[trip_col].map(parse_any_date)
        out = out[trip_dates.notna()].copy()
        if out.empty:
            return out.reset_index(drop=True)

        out["_loading_trip_date"] = trip_dates.loc[out.index]
        month_prefix = f"{month_key}-"
        out = out[out["_loading_trip_date"].map(lambda value: value.isoformat().startswith(month_prefix))].copy()
        return out.reset_index(drop=True)

    def build_loading_month_page(state: SourceState, selected_month_raw: Optional[str], selected_cargo_raw: Optional[str]) -> str:
        selected_month = normalize_month_key(selected_month_raw, state.report_dt or now())
        archive_index = prune_archive(load_archive_index())
        archive_items = list(archive_index.get(TAB_DEPARTURE, []))
        month_prefix = f"{selected_month}-"
        month_records: list[dict[str, object]] = []
        archive_days: set[str] = set()
        info_parts: list[str] = []

        def _process_state(day_state: SourceState, archive_day_key: str) -> None:
            day_df = filter_loading_month_frame(day_state.df, selected_month)
            month_records.extend(build_day_records(day_df, selected_month))
            archive_days.add(archive_day_key)

        for item in sorted(archive_items, key=lambda value: str(value.get("archive_date") or "")):
            archive_day = str(item.get("archive_date") or "")
            if not archive_day.startswith(month_prefix):
                continue
            file_path = Path(str(item.get("file_path") or ""))
            if not file_path.exists():
                continue
            try:
                day_state = build_state_from_path(
                    str(file_path),
                    mode=TAB_DEPARTURE,
                    source_name=str(item.get("source_name") or file_path.name),
                    source_kind="archive",
                    mail_signature=None,
                )
                _process_state(day_state, archive_day)
            except Exception:
                continue

        live_day = state.report_dt.date().isoformat() if state and state.report_dt else ""
        if live_day.startswith(month_prefix) and live_day not in archive_days:
            _process_state(state, live_day)
            info_parts.append(f"В расчёт включена текущая справка за {state.report_dt.strftime('%d.%m.%Y')}, так как архив за этот день ещё не найден.")

        report = build_loading_month_report(month_records, selected_month, archive_days, selected_cargo_raw)
        if not archive_days:
            info_parts.append("Для выбранного месяца в архиве пока нет сохранённых справок погрузки.")

        return render_page(
            LOADING_MONTH_BODY,
            title=f"{APP_TITLE} — Погрузка с начала месяца",
            app_title=APP_TITLE,
            current_tab=TAB_LOADING,
            loading_mode="month",
            selected_month=selected_month,
            source_name=state.source_name if state else "Источник данных ещё не загружен",
            source_time=state.loaded_at.strftime("Обновлено %d.%m.%Y %H:%M:%S") if state else "",
            report_date_label=state.report_dt.strftime("%d.%m.%Y %H:%M") if state and state.report_dt else "",
            archive_date="",
            success_message=pop_success(),
            error_message=pop_error(),
            info_message=" ".join(info_parts).strip(),
            report=report,
        )

    def _password_hash(value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

    def load_stop_rent_security() -> dict:
        data = load_json_file(stop_rent_security_path, {})
        if not isinstance(data, dict):
            data = {}
        if not data.get("password_hash"):
            data["password_hash"] = _password_hash(STOP_RENT_DEFAULT_PASSWORD)
        data.setdefault("failed_attempts", 0)
        data.setdefault("reset_request_code", "")
        data.setdefault("reset_requested_at", "")
        return data

    def save_stop_rent_security(data: dict) -> None:
        save_json_file(stop_rent_security_path, data)

    def verify_stop_rent_password(value: str) -> bool:
        data = load_stop_rent_security()
        ok = data.get("password_hash") == _password_hash(value or "")
        if ok:
            data["failed_attempts"] = 0
        else:
            data["failed_attempts"] = int(data.get("failed_attempts", 0) or 0) + 1
        save_stop_rent_security(data)
        return ok

    def set_stop_rent_password(value: str) -> None:
        data = load_stop_rent_security()
        data["password_hash"] = _password_hash(value)
        data["failed_attempts"] = 0
        data["reset_request_code"] = ""
        data["reset_requested_at"] = ""
        save_stop_rent_security(data)

    def create_stop_rent_request_code() -> str:
        stamp = now().strftime("%Y%m%d")
        nonce = secrets.token_hex(3).upper()
        return f"SR-{stamp}-{nonce}"

    def b64u_decode(text_value: str) -> bytes:
        text_value = (text_value or "").strip()
        padding = "=" * (-len(text_value) % 4)
        return base64.urlsafe_b64decode(text_value + padding)

    def load_stop_rent_reset_public_key() -> Ed25519PublicKey:
        if not stop_rent_reset_public_key_path.exists():
            raise FileNotFoundError(
                f"Не найден файл открытого ключа сброса пароля: {stop_rent_reset_public_key_path}"
            )
        raw = stop_rent_reset_public_key_path.read_bytes()
        key = serialization.load_pem_public_key(raw)
        if not isinstance(key, Ed25519PublicKey):
            raise TypeError("Ожидался открытый ключ Ed25519 для сброса пароля.")
        return key

    def verify_stop_rent_recovery_code(request_code: str, recovery_code: str) -> tuple[bool, str]:
        request_code = (request_code or "").strip()
        recovery_code = (recovery_code or "").strip()
        if not request_code:
            return False, "Сначала сформируйте код запроса."
        if not recovery_code:
            return False, "Код восстановления не указан."
        try:
            token_bytes = b64u_decode(recovery_code)
            envelope = json.loads(token_bytes.decode("utf-8"))
            if not isinstance(envelope, dict):
                return False, "Неверный формат кода восстановления."
            payload_b64 = str(envelope.get("payload") or "")
            sig_b64 = str(envelope.get("sig") or "")
            alg = str(envelope.get("alg") or "")
            if alg != "Ed25519" or not payload_b64 or not sig_b64:
                return False, "Неверный формат кода восстановления."
            payload_bytes = b64u_decode(payload_b64)
            signature = b64u_decode(sig_b64)
            public_key = load_stop_rent_reset_public_key()
            public_key.verify(signature, payload_bytes)
            payload = json.loads(payload_bytes.decode("utf-8"))
            if not isinstance(payload, dict):
                return False, "Неверное содержимое кода восстановления."
            if str(payload.get("purpose") or "") != "STOP_RENT_PASSWORD_RESET":
                return False, "Код восстановления не предназначен для сброса пароля."
            if str(payload.get("req") or "").strip() != request_code:
                return False, "Код восстановления не подходит к текущему коду запроса."
            return True, ""
        except FileNotFoundError as exc:
            return False, str(exc)
        except InvalidSignature:
            return False, "Подпись кода восстановления неверна."
        except Exception:
            return False, "Неверный формат кода восстановления."

    def issue_stop_rent_reset_request() -> str:
        data = load_stop_rent_security()
        request_code = create_stop_rent_request_code()
        data["reset_request_code"] = request_code
        data["reset_requested_at"] = now().isoformat()
        save_stop_rent_security(data)
        return request_code

    def is_stop_rent_authenticated(tab: str) -> bool:
        value = session.get("stop_rent_auth", {})
        return isinstance(value, dict) and value.get(tab) is True

    def set_stop_rent_authenticated(tab: str, value: bool) -> None:
        data = session.get("stop_rent_auth", {})
        if not isinstance(data, dict):
            data = {}
        data[tab] = bool(value)
        session["stop_rent_auth"] = data

    def get_license_snapshot() -> dict:
        state = get_license_state(base_dir, app.config["LICENSE_SETTINGS"])
        return {
            "license_active": state.active,
            "license_reason": state.reason,
            "license_payload": state.license_payload or {},
            "device_code": state.device_code,
            "device_name": state.device_name,
            "os_user": state.os_user,
            "storage_dir": state.storage_dir,
            "local_license_path": state.local_license_path,
            "app_version": str(app.config["LICENSE_SETTINGS"].get("current_version") or ""),
        }

    def get_update_snapshot() -> dict:
        return get_update_info(app.config["LICENSE_SETTINGS"])

    def get_tab_name(raw_value: Optional[str]) -> str:
        if raw_value in {None, "", TAB_DASHBOARD}:
            return TAB_DASHBOARD
        if raw_value == TAB_DEPARTURE:
            return TAB_DEPARTURE
        if raw_value == TAB_STATION_IDLE:
            return TAB_STATION_IDLE
        if raw_value == TAB_LOADING:
            return TAB_LOADING
        if raw_value == TAB_RAW_MATERIAL:
            return TAB_RAW_MATERIAL
        if raw_value == TAB_MANUAL:
            return TAB_MANUAL
        if raw_value == TAB_ARCHIVE:
            return TAB_ARCHIVE
        if raw_value == TAB_STATION_SELECT:
            return TAB_STATION_SELECT
        if raw_value == TAB_SETTINGS:
            return TAB_SETTINGS
        return TAB_APPROACH

    def get_source_tab(tab: str) -> str:
        if tab == TAB_STATION_IDLE:
            return TAB_APPROACH
        if tab == TAB_LOADING:
            return TAB_DEPARTURE
        if tab == TAB_RAW_MATERIAL:
            return TAB_APPROACH
        return tab

    def set_error(message: Optional[str]) -> None:
        app.config["LAST_ERROR"] = message

    def set_success(message: Optional[str]) -> None:
        app.config["LAST_SUCCESS"] = message

    def pop_error() -> Optional[str]:
        message = app.config.get("LAST_ERROR")
        app.config["LAST_ERROR"] = None
        return message

    def pop_success() -> Optional[str]:
        message = app.config.get("LAST_SUCCESS")
        app.config["LAST_SUCCESS"] = None
        return message

    def get_state(tab: str) -> Optional[SourceState]:
        return app.config.get("CURRENT_STATES", {}).get(tab)

    def set_state(tab: str, state: Optional[SourceState]) -> None:
        app.config["CURRENT_STATES"][tab] = state

    def email_enabled(tab: str) -> bool:
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return False
        return bool(get_imap_config(_effective_mail_settings_for_tab(tab), tab).get("enabled"))

    def is_card_only_view(
        tab: str,
        destination: Optional[str],
        origin: Optional[str],
        train_index: Optional[str] = None,
        trip_start: Optional[str] = None,
    ) -> bool:
        if tab == TAB_STATION_IDLE:
            return False
        if train_index or trip_start:
            return False
        return (tab == TAB_DEPARTURE and _is_departure_direction(destination)) or (tab == TAB_APPROACH and _is_approach_direction(origin))

    def parse_iso_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value))
        except Exception:
            return None

    def to_iso(dt: Optional[datetime]) -> str:
        return dt.isoformat() if isinstance(dt, datetime) else ""

    def from_iso_datetime(value: object) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def load_json_file(path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save_json_file(path: Path, payload) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_archive_index() -> dict[str, list[dict]]:
        data = load_json_file(archive_meta_path, {})
        if not isinstance(data, dict):
            return {}
        return data

    def prune_archive(index: dict[str, list[dict]]) -> dict[str, list[dict]]:
        cutoff = now().date() - timedelta(days=365)
        cleaned: dict[str, list[dict]] = {}
        for tab, items in index.items():
            cleaned_items: list[dict] = []
            for item in items if isinstance(items, list) else []:
                archive_date = parse_iso_date(item.get("archive_date"))
                file_path = Path(str(item.get("file_path") or ""))
                if archive_date is None or archive_date < cutoff:
                    if file_path.exists():
                        try:
                            file_path.unlink()
                        except Exception:
                            pass
                    continue
                if not file_path.exists():
                    continue
                cleaned_items.append(item)
            cleaned[tab] = cleaned_items
        return cleaned

    def save_archive_index(index: dict[str, list[dict]]) -> None:
        save_json_file(archive_meta_path, index)

    def _archive_item_matches_current_station(item: dict) -> bool:
        station = get_selected_station_name() or DEFAULT_WORK_STATION
        current_key = normalize_station_key(station)
        item_key = normalize_station_key(item.get("station") or item.get("station_key"))
        if not item_key:
            return is_base_station(station)
        return item_key == current_key

    def maybe_register_archive(tab: str, report_dt: datetime, file_path: str, source_name: str) -> None:
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return

        index = prune_archive(load_archive_index())

        archive_day = now().date().isoformat()
        tab_items = list(index.get(tab, []))
        station = get_selected_station_name() or DEFAULT_WORK_STATION
        station_key = normalize_station_key(station)

        for item in tab_items:
            if item.get("archive_date") == archive_day and _archive_item_matches_current_station(item):
                save_archive_index(index)
                return

        if is_base_station(station):
            target_dir = archive_dir / tab
        else:
            target_dir = archive_dir / "stations" / _station_slug(station) / tab
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = secure_filename(Path(file_path).name) or f"{tab}_{archive_day}.xlsx"
        target_path = target_dir / f"{archive_day}_{report_dt.strftime('%H%M%S')}_{safe_name}"
        shutil.copy2(file_path, target_path)

        current_meta = {
            "archive_date": archive_day,
            "report_dt": report_dt.isoformat(),
            "source_name": source_name,
            "file_path": str(target_path),
            "saved_at": now().isoformat(),
            "station": station,
            "station_key": station_key,
        }

        tab_items.append(current_meta)
        tab_items.sort(key=lambda item: (item.get("archive_date") or "", item.get("station_key") or ""))
        index[tab] = tab_items
        save_archive_index(index)

    def get_archived_state(source_tab: str, archive_date: str) -> Optional[SourceState]:
        archive_index = prune_archive(load_archive_index())
        save_archive_index(archive_index)
        for item in archive_index.get(source_tab, []):
            if item.get("archive_date") != archive_date or not _archive_item_matches_current_station(item):
                continue
            file_path = Path(str(item.get("file_path") or ""))
            if not file_path.exists():
                continue
            df = load_excel_as_df(str(file_path), mode=source_tab)
            report_dt = from_iso_datetime(item.get("report_dt")) or parse_report_datetime(str(file_path)) or now()
            return SourceState(
                df=df,
                source_name=f"Архив: {item.get('source_name') or file_path.name}",
                loaded_at=now(),
                report_dt=report_dt,
                file_path=str(file_path),
                source_kind="archive",
                mail_signature=None,
                mode=source_tab,
            )
        return None

    def list_archived_dates(source_tab: str) -> list[str]:
        archive_index = prune_archive(load_archive_index())
        save_archive_index(archive_index)
        dates: list[str] = []
        for item in archive_index.get(source_tab, []):
            archive_day = str(item.get("archive_date") or "").strip()
            if archive_day and _archive_item_matches_current_station(item):
                dates.append(archive_day)
        return sorted(set(dates))

    def load_stop_rent_records() -> list[dict]:
        data = load_json_file(stop_rent_path, [])
        return data if isinstance(data, list) else []

    def save_stop_rent_records(records: list[dict]) -> None:
        save_json_file(stop_rent_path, records)

    def update_stop_rent_from_state(tab: str, state: SourceState) -> None:
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return
        records = load_stop_rent_records()
        changed = False
        for record in records:
            if record.get("tab") != tab or record.get("ended_at"):
                continue
            wagon = normalize_wagon_number(record.get("wagon_number", ""))
            matches = state.df[state.df["Номер вагона"].map(normalize_wagon_number) == wagon]
            if matches.empty:
                continue
            row = matches.iloc[0]
            record["raw_kind"] = strip_last_numeric_code(row.get("Род вагона", ""))
            record["operation"] = strip_last_numeric_code(row.get("Операция с вагоном", ""))
            record["operation_time"] = str(row.get("Дата и время операции", ""))
            if is_stop_rent_end_operation(row.get("Операция с вагоном", "")):
                operation_dt = pd.to_datetime(row.get("Дата и время операции", ""), dayfirst=True, errors="coerce")
                ended_at = operation_dt.to_pydatetime().replace(tzinfo=None) if not pd.isna(operation_dt) else state.report_dt
                record["ended_at"] = to_iso(ended_at)
                record["end_date"] = ended_at.date().isoformat()
                record["end_operation"] = str(row.get("Операция с вагоном", ""))
                record["end_operation_time"] = str(row.get("Дата и время операции", ""))
            changed = True
        if changed:
            save_stop_rent_records(records)

    def format_ru_date(value: Optional[str]) -> str:
        parsed = parse_iso_date(value)
        return parsed.strftime("%d.%m.%Y") if parsed else str(value or "")

    def _stop_rent_legacy_group_stamp(record: dict) -> str:
        for field in ("batch_created_at", "created_at"):
            value = str(record.get(field) or "").strip()
            if not value:
                continue
            parsed = from_iso_datetime(value)
            if parsed is not None:
                return parsed.replace(microsecond=0).isoformat()
            return value[:19] if len(value) >= 19 else value
        return ""

    def get_stop_rent_batch_key(record: dict) -> str:
        batch_id = str(record.get("batch_id") or "").strip()
        batch_created_at = str(record.get("batch_created_at") or "").strip()
        if batch_id and batch_created_at:
            return batch_id
        legacy_stamp = _stop_rent_legacy_group_stamp(record)
        if legacy_stamp:
            return f"legacy-group-{record.get('tab')}-{record.get('station')}-{record.get('start_date')}-{legacy_stamp}"
        if batch_id:
            return batch_id
        record_id = str(record.get("id") or "").strip()
        if record_id:
            return f"legacy-{record_id}"
        return f"legacy-{record.get('tab')}-{record.get('station')}-{record.get('wagon_number')}-{record.get('start_date')}"

    def enrich_stop_rent_record(record: dict, as_of_dt: datetime) -> Optional[dict]:
        as_of_date = as_of_dt.date()
        start_date = parse_iso_date(record.get("start_date"))
        if start_date is None or start_date > as_of_date:
            return None
        ended_at = from_iso_datetime(record.get("ended_at"))
        end_date = ended_at.date() if ended_at else None
        if end_date is not None and end_date + timedelta(days=3) < as_of_date:
            return None
        record_copy = dict(record)
        record_copy["batch_id"] = get_stop_rent_batch_key(record)
        record_copy["wagon_number"] = normalize_wagon_number(record.get("wagon_number", ""))
        record_copy["raw_kind"] = strip_last_numeric_code(record.get("raw_kind", ""))
        record_copy["operation"] = strip_last_numeric_code(record.get("operation", record.get("end_operation", "")))
        record_copy["operation_time"] = str(record.get("operation_time") or record.get("end_operation_time") or "")
        record_copy["status_label"] = "Активна" if ended_at is None or end_date > as_of_date else "Завершена"
        days = whole_calendar_days(start_date.isoformat(), (ended_at or as_of_dt))
        record_copy["days_display"] = str(days) if days is not None else "—"
        return record_copy

    def get_visible_stop_rent_records(tab: str, as_of_dt: Optional[datetime]) -> list[dict]:
        as_of_dt = as_of_dt or now()
        visible: list[dict] = []
        for record in load_stop_rent_records():
            if record.get("tab") != tab:
                continue
            enriched = enrich_stop_rent_record(record, as_of_dt)
            if enriched is not None:
                visible.append(enriched)
        visible.sort(key=lambda item: (item.get("ended_at") or "9999", item.get("start_date") or "", item.get("wagon_number") or ""))
        return visible

    def get_stop_rent_groups(tab: str, as_of_dt: Optional[datetime]) -> list[dict]:
        records = get_visible_stop_rent_records(tab, as_of_dt)
        grouped: dict[str, list[dict]] = {}
        for record in records:
            grouped.setdefault(record["batch_id"], []).append(record)
        groups: list[dict] = []
        for batch_id, items in grouped.items():
            items.sort(key=lambda item: item.get("wagon_number") or "")
            station_names = ", ".join(sorted({str(item.get("station") or "") for item in items if str(item.get("station") or "").strip()})) or "—"
            active_count = sum(1 for item in items if item.get("status_label") == "Активна")
            ended_count = len(items) - active_count
            if active_count and ended_count:
                status_summary = f"Активна {active_count}, завершена {ended_count}"
            elif active_count:
                status_summary = f"Активна, вагонов: {active_count}"
            else:
                status_summary = f"Завершена, вагонов: {len(items)}"
            start_date = items[0].get("start_date") or ""
            groups.append({
                "batch_id": batch_id,
                "title": f"Стоп аренда {len(items)} вагонов от {format_ru_date(start_date)} г.",
                "count": len(items),
                "station_names": station_names,
                "status_summary": status_summary,
                "start_date": start_date,
                "records": items,
            })
        groups.sort(key=lambda item: item.get("start_date") or "", reverse=True)
        return groups

    def get_stop_rent_group(tab: str, batch_id: str, as_of_dt: Optional[datetime]) -> Optional[dict]:
        if not batch_id:
            return None
        for group in get_stop_rent_groups(tab, as_of_dt):
            if group.get("batch_id") == batch_id:
                return group
        return None

    def remove_stop_rent_selected(tab: str, batch_id: str, wagon_numbers: list[str]) -> int:
        if not batch_id or not wagon_numbers:
            return 0
        targets = {normalize_wagon_number(value) for value in wagon_numbers if normalize_wagon_number(value)}
        if not targets:
            return 0
        records = load_stop_rent_records()
        kept: list[dict] = []
        removed = 0
        for record in records:
            if record.get("tab") == tab and get_stop_rent_batch_key(record) == batch_id and normalize_wagon_number(record.get("wagon_number", "")) in targets:
                removed += 1
                continue
            kept.append(record)
        if removed:
            save_stop_rent_records(kept)
        return removed

    def remove_stop_rent_batch(tab: str, batch_id: str) -> int:
        if not batch_id:
            return 0
        records = load_stop_rent_records()
        kept: list[dict] = []
        removed = 0
        for record in records:
            if record.get("tab") == tab and get_stop_rent_batch_key(record) == batch_id:
                removed += 1
                continue
            kept.append(record)
        if removed:
            save_stop_rent_records(kept)
        return removed

    def create_stop_rent_records(tab: str, station: str, wagon_numbers: list[str], start_date: str, station_rows: Optional[dict[str, dict]] = None) -> int:
        records = load_stop_rent_records()
        existing_active = {
            (record.get("tab"), normalize_wagon_number(record.get("wagon_number", "")))
            for record in records
            if not record.get("ended_at")
        }
        created = 0
        batch_id = uuid.uuid4().hex
        batch_created_at = now().replace(microsecond=0).isoformat()
        station_rows = station_rows or {}
        for wagon_number in wagon_numbers:
            normalized = normalize_wagon_number(wagon_number)
            if not normalized or (tab, normalized) in existing_active:
                continue
            source_row = station_rows.get(normalized, {})
            records.append(
                {
                    "id": uuid.uuid4().hex,
                    "batch_id": batch_id,
                    "batch_created_at": batch_created_at,
                    "tab": tab,
                    "station": station,
                    "wagon_number": normalized,
                    "raw_kind": strip_last_numeric_code(source_row.get("Род вагона", "")),
                    "operation": strip_last_numeric_code(source_row.get("Операция с вагоном", "")),
                    "operation_time": str(source_row.get("Дата и время операции", "")),
                    "start_date": start_date,
                    "created_at": batch_created_at,
                    "ended_at": "",
                    "end_date": "",
                    "end_operation": "",
                    "end_operation_time": "",
                }
            )
            existing_active.add((tab, normalized))
            created += 1
        if created:
            save_stop_rent_records(records)
        return created


    def _positive_distance_df(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty or "Расстояние оставшееся (км)" not in frame.columns:
            return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()
        out = frame[frame["Расстояние оставшееся (км)"].map(lambda v: (parse_distance_km(v) or 0) > 0)].copy()
        return out.reset_index(drop=True)

    def _exclude_ugleuralskaya_rows(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None:
            return pd.DataFrame()
        if frame.empty or "Станция операции" not in frame.columns:
            return frame.copy()
        out = frame[~frame["Станция операции"].map(_station_matches_selected)].copy()
        return out.reset_index(drop=True)

    _SPECIAL_APPROACH_CARD_BASES = {"ЗАБАЙКАЛЬСК", "ЕЙСК"}

    def _normalize_special_approach_card_base(value: object) -> str:
        text_value = normalize_spaces(value).upper().replace("Ё", "Е")
        return text_value

    def _matches_special_approach_card_origin(value: object, base_name: str) -> bool:
        text_value = normalize_spaces(value).upper().replace("Ё", "Е")
        return bool(text_value) and (text_value == base_name or text_value.startswith(base_name + " ("))

    def _is_tank_kind_value(value: object) -> bool:
        return "ЦИСТЕР" in normalize_spaces(value).upper().replace("Ё", "Е")

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

    def _apply_special_detail_source_filters(
        tab: str,
        frame: pd.DataFrame,
        destination: Optional[str],
        origin: Optional[str],
    ) -> pd.DataFrame:
        if frame is None:
            return pd.DataFrame()
        out = frame.copy()
        if tab == TAB_DEPARTURE:
            out = _positive_distance_df(out)
        if tab == TAB_APPROACH:
            special_origin_base = _normalize_special_approach_card_base(origin)
            if special_origin_base in _SPECIAL_APPROACH_CARD_BASES:
                required_cols = {"Станция отправления", "Станция операции", "Род вагона", "Расстояние оставшееся (км)"}
                if not required_cols.issubset(set(out.columns)):
                    return out.iloc[0:0].copy()
                out = out[
                    out["Станция отправления"].map(lambda value: _matches_special_approach_card_origin(value, special_origin_base))
                    & out["Станция операции"].map(lambda value: not is_ugleuralskaya_station(value))
                    & out["Род вагона"].map(_is_tank_kind_value)
                    & out["Расстояние оставшееся (км)"].map(lambda value: (parse_distance_km(value) or 0) > 0)
                ].copy()
                if "train_index_normalized" in out.columns:
                    out = out[out["train_index_normalized"].map(normalize_spaces).ne("")].copy()
                elif "Индекс поезда" in out.columns:
                    out = out[out["Индекс поезда"].map(normalize_spaces).ne("")].copy()
                else:
                    return out.iloc[0:0].copy()
        return out.reset_index(drop=True)

    def format_tons(value: object) -> str:
        text = str(value or "").replace(" ", "").replace(",", ".")
        if not text:
            return ""
        try:
            num = float(text)
            return f"{num / 1000:.3f}".rstrip("0").rstrip(".")
        except Exception:
            return str(value or "")

    def _normalize_station_directory_key(value: object) -> str:
        text_value = strip_last_numeric_code(value or "")
        text_value = str(text_value or "").upper().replace("Ё", "Е")
        text_value = " ".join(text_value.replace("\xa0", " ").split())
        return text_value

    def _station_directory_key_variants(value: object) -> list[str]:
        base = _normalize_station_directory_key(value)
        variants: list[str] = []

        def _push(item: str) -> None:
            item = str(item or "").strip()
            if item and item not in variants:
                variants.append(item)

        _push(base)
        if base:
            no_paren = " ".join(re.sub(r"\([^)]*\)", " ", base).split())
            _push(no_paren)
            no_quotes = base.replace('"', '').replace("'", "")
            _push(no_quotes)
            _push(no_quotes.replace("-", " "))
            _push(base.replace(" ", ""))
            if no_paren:
                _push(no_paren.replace("-", " "))
                _push(no_paren.replace(" ", ""))
        return variants

    def load_station_directory() -> dict:
        cache = app.config.get("STATION_DIRECTORY_CACHE")
        station_path = get_user_data_file(STATION_DIRECTORY_FILE)
        signature = None
        if station_path.exists():
            stat = station_path.stat()
            signature = (str(station_path), stat.st_mtime_ns, stat.st_size)
        if cache and cache.get("signature") == signature:
            return cache

        result = {
            "signature": signature,
            "available": False,
            "path": str(station_path),
            "items": [],
            "by_key": {},
            "record_count": 0,
            "error": "",
        }

        if not station_path.exists():
            app.config["STATION_DIRECTORY_CACHE"] = result
            return result

        try:
            payload = json.loads(station_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("stations"), list):
                raw_items = payload.get("stations", [])
            elif isinstance(payload, list):
                raw_items = payload
            else:
                raw_items = []

            by_key: dict[str, dict] = {}
            items: list[dict] = []
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                lat = raw.get("latitude", raw.get("lat"))
                lng = raw.get("longitude", raw.get("lng"))
                try:
                    lat_value = float(lat)
                    lng_value = float(lng)
                except Exception:
                    continue

                item = {
                    "name": str(raw.get("name") or "").strip(),
                    "normalized_name": str(raw.get("normalized_name") or raw.get("name") or "").strip(),
                    "code": str(raw.get("code") or "").strip(),
                    "latitude": lat_value,
                    "longitude": lng_value,
                    "railway_name": str(raw.get("railway_name") or "").strip(),
                    "railway_short_name": str(raw.get("railway_short_name") or "").strip(),
                }
                items.append(item)
                for key in _station_directory_key_variants(item["normalized_name"]):
                    by_key.setdefault(key, item)
                for key in _station_directory_key_variants(item["name"]):
                    by_key.setdefault(key, item)
                if item["code"]:
                    by_key.setdefault(item["code"], item)

            result.update({
                "available": bool(items),
                "items": items,
                "by_key": by_key,
                "record_count": len(items),
            })
        except Exception as exc:
            result["error"] = str(exc)

        app.config["STATION_DIRECTORY_CACHE"] = result
        return result

    def lookup_station_coordinates(station_name: object) -> Optional[dict]:
        directory = load_station_directory()
        by_key = directory.get("by_key", {}) if isinstance(directory, dict) else {}
        for key in _station_directory_key_variants(station_name):
            item = by_key.get(key)
            if item:
                return item
        return None

    def _build_filtered_view(
        tab: str,
        state: SourceState,
        archive_date: str,
        idle_view: str,
        loading_view: str,
        road: Optional[str],
        station: Optional[str],
        kind: Optional[str],
        cargo: Optional[str],
        wagon: Optional[str],
        destination: Optional[str],
        origin: Optional[str],
        train_index: Optional[str],
        trip_start: Optional[str],
        formed_trains: bool,
        overdue_delivery: bool,
        primary_only: bool,
        idle_bucket: Optional[str],
        exclude_ugleuralskaya: bool = False,
        raw_material_cargo: Optional[str] = None,
        raw_material_days: Optional[int] = None,
        cargo_name_filter: Optional[str] = None,
        trip_end_date: Optional[str] = None,
        departure_acceptance_date: Optional[str] = None,
    ) -> pd.DataFrame:
        if tab == TAB_STATION_IDLE:
            primary_only = False
            effective_idle_mode = idle_view
        else:
            effective_idle_mode = None
        if tab == TAB_RAW_MATERIAL:
            primary_only = False

        source_df = state.df
        if tab == TAB_APPROACH:
            source_df = _apply_approach_header_filters(
                source_df,
                normalize_spaces(request.args.get("approach_cargo_filter")),
                normalize_spaces(request.args.get("approach_previous_cargo_filter")),
            )
        if tab == TAB_LOADING:
            source_df = filter_loading_view(source_df, state.report_dt, loading_view)
        elif tab == TAB_RAW_MATERIAL:
            source_df = filter_raw_material_idle(source_df, state.report_dt, raw_material_cargo, raw_material_days)
        source_df = _apply_special_detail_source_filters(tab, source_df, destination, origin)
        if exclude_ugleuralskaya and tab == TAB_APPROACH:
            source_df = _exclude_ugleuralskaya_rows(source_df)

        special_approach_card = tab == TAB_APPROACH and _normalize_special_approach_card_base(origin) in _SPECIAL_APPROACH_CARD_BASES
        effective_origin = origin
        effective_kind = kind
        effective_primary_only = primary_only
        if special_approach_card:
            effective_origin = None
            effective_kind = None
            effective_primary_only = False
        elif tab == TAB_APPROACH and _is_approach_direction(origin) and not effective_kind:
            effective_kind = "ЦС"

        if tab == TAB_DEPARTURE:
            source_df = _with_departure_acceptance_display(source_df)

        return filter_detail(
            source_df,
            road=road,
            station=station,
            kind=effective_kind,
            cargo=cargo,
            exact_wagon=wagon,
            report_dt=state.report_dt,
            formed_trains=formed_trains,
            destination=destination,
            origin=effective_origin,
            train_index=train_index,
            trip_start=trip_start,
            overdue_delivery=overdue_delivery,
            primary_destination_only=effective_primary_only,
            idle_bucket=idle_bucket,
            idle_mode=effective_idle_mode,
            cargo_name_value=cargo_name_filter,
            trip_end_date=trip_end_date,
            departure_acceptance_date=departure_acceptance_date,
        )

    def build_map_link(
        tab: str,
        archive_date: Optional[str] = None,
        idle_view: Optional[str] = None,
        loading_view: Optional[str] = None,
        road: Optional[str] = None,
        station: Optional[str] = None,
        destination: Optional[str] = None,
        origin: Optional[str] = None,
        idle_bucket: Optional[str] = None,
        formed_trains: bool = False,
        overdue_delivery: bool = False,
        primary_only: bool = False,
        cargo_name_filter: Optional[str] = None,
    ) -> str:
        params = {
            "tab": tab,
        }
        if archive_date:
            params["archive_date"] = archive_date
        if idle_view:
            params["idle_view"] = idle_view
        if loading_view:
            params["loading_view"] = loading_view
        if road:
            params["road"] = road
        if station:
            params["station"] = station
        if destination:
            params["destination"] = destination
        if origin:
            params["origin"] = origin
        if idle_bucket:
            params["idle_bucket"] = idle_bucket
        if formed_trains:
            params["formed_trains"] = "1"
        if overdue_delivery:
            params["overdue"] = "1"
        if primary_only:
            params["primary_only"] = "1"
        if cargo_name_filter:
            params["cargo_name_filter"] = cargo_name_filter
        if tab == TAB_APPROACH:
            approach_cargo_filter = normalize_spaces(request.args.get("approach_cargo_filter"))
            approach_previous_cargo_filter = normalize_spaces(request.args.get("approach_previous_cargo_filter"))
            if approach_cargo_filter:
                params["approach_cargo_filter"] = approach_cargo_filter
            if approach_previous_cargo_filter:
                params["approach_previous_cargo_filter"] = approach_previous_cargo_filter
        return url_for("station_map") + "?" + urlencode(params)

    def _map_wagon_record(row: pd.Series) -> dict:
        station_value = row.get("station_display", "") or row.get("Станция операции", "")
        road_value = row.get("road_display", "") or row.get("Дорога операции", "")
        cargo_state = str(row.get("cargo_state", "") or "").strip().lower()
        cargo_label = "Гружёный" if cargo_state == "гр" else "Порожний"
        return {
            "wagon_number": normalize_wagon_number(row.get("Номер вагона", "")),
            "station": station_value,
            "road": road_value,
            "cargo_label": cargo_label,
            "raw_kind": strip_last_numeric_code(row.get("Род вагона", "")),
            "operation_time": str(row.get("Дата и время операции", "") or "").strip(),
        }

    def build_map_points(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
        grouped: dict[str, dict] = {}
        unresolved: dict[str, int] = defaultdict(int)
        if df is None or df.empty:
            return [], []

        for _, row in df.iterrows():
            wagon = _map_wagon_record(row)
            station_name = wagon["station"]
            station_info = lookup_station_coordinates(station_name)
            if not station_info:
                unresolved[station_name or "Станция операции не указана"] += 1
                continue
            group_key = str(station_info.get("code") or station_info.get("normalized_name") or station_info.get("name") or station_name)
            point = grouped.get(group_key)
            if point is None:
                point = {
                    "station_name": str(station_info.get("name") or station_name),
                    "road_name": wagon["road"] or str(station_info.get("railway_name") or station_info.get("railway_short_name") or ""),
                    "latitude": float(station_info["latitude"]),
                    "longitude": float(station_info["longitude"]),
                    "code": str(station_info.get("code") or ""),
                    "wagons": [],
                }
                grouped[group_key] = point
            point["wagons"].append(wagon)

        points: list[dict] = []
        for point in grouped.values():
            point["wagons"].sort(key=lambda item: item.get("wagon_number") or "")
            point["count"] = len(point["wagons"])
            point["search_blob"] = " ".join(
                filter(
                    None,
                    [
                        point["station_name"],
                        point["road_name"],
                        " ".join(item.get("wagon_number") or "" for item in point["wagons"]),
                    ],
                )
            )
            points.append(point)

        points.sort(key=lambda item: (-item["count"], item["station_name"]))
        unresolved_items = [
            {"name": name, "count": count}
            for name, count in sorted(unresolved.items(), key=lambda item: (-item[1], item[0]))
        ]
        return points, unresolved_items

    def build_state_from_path(file_path: str, mode: str, source_name: Optional[str] = None, source_kind: str = "file", mail_signature: Optional[str] = None) -> SourceState:
        df = load_excel_as_df(file_path, mode=mode)
        report_dt = parse_report_datetime(file_path) or now()
        return SourceState(
            df=df,
            source_name=source_name or Path(file_path).name,
            loaded_at=now(),
            report_dt=report_dt,
            file_path=file_path,
            source_kind=source_kind,
            mail_signature=mail_signature,
            mode=mode,
        )

    def apply_loaded_state(mode: str, state: SourceState) -> None:
        set_state(mode, state)
        if state.file_path:
            maybe_register_archive(mode, state.report_dt, state.file_path, state.source_name)
        update_stop_rent_from_state(mode, state)
        if state.source_kind == "mail" and state.file_path:
            remove_previous_mail_files(mail_dir, mode, keep_path=Path(state.file_path))
        # Претензии пересчитываются лениво — только при открытии раздела
        # «Претензии». Загрузка/автообновление справок не должны запускать
        # тяжёлый расчёт претензий и тормозить остальные разделы.
        set_error(None)

    def validate_mail_candidate_state(tab: str, state: SourceState) -> tuple[bool, str]:
        df = state.df
        # Пропускаем валидацию для пустых данных - это может быть нормально 
        # когда используются заглушки в core модуле
        if df is None or df.empty:
            return True, ""  # Принимаем файл даже если данные пусты
        if "Номер вагона" not in df.columns:
            return False, "В файле отсутствует столбец 'Номер вагона'."
        valid_wagons = df["Номер вагона"].map(normalize_wagon_number)
        valid_count = int(valid_wagons.map(lambda value: len(value) == 8 and value.isdigit()).sum())
        if valid_count == 0:
            return False, "В файле нет корректных номеров вагонов."
        display_rows = build_summary_rows(df)
        if not display_rows:
            return True, ""  # Принимаем файл даже если нет display rows
        return True, ""

    def load_from_path(file_path: str, mode: str, source_name: Optional[str] = None, source_kind: str = "file", mail_signature: Optional[str] = None) -> None:
        state = build_state_from_path(file_path, mode=mode, source_name=source_name, source_kind=source_kind, mail_signature=mail_signature)
        apply_loaded_state(mode, state)

    def try_mail_sync(tab: str, force: bool = False) -> Optional[MailFetchResult]:
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return None
        with mail_sync_lock:
            # Try to load from local folder first, then from mail
            try:
                result = fetch_latest_excel_from_folder(_station_mail_dir(), tab)
            except Exception:
                # Fallback to email if folder not available and email is enabled
                if not email_enabled(tab):
                    raise
                result = fetch_latest_excel_from_mail(_effective_mail_settings_for_tab(tab), _station_mail_dir(), tab)
            current_state = get_state(tab)
            if not force and current_state is not None and current_state.source_kind == "mail" and current_state.mail_signature and current_state.mail_signature == result.signature:
                try:
                    Path(result.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                return None
            is_from_folder = result.signature.startswith("folder::")
            source_name = f"Папка: {result.display_name}" if is_from_folder else f"Почта: {result.display_name}"
            candidate_state = build_state_from_path(
                result.file_path,
                mode=tab,
                source_name=source_name,
                source_kind="mail",
                mail_signature=result.signature,
            )
            is_valid, reason = validate_mail_candidate_state(tab, candidate_state)
            if not is_valid:
                try:
                    Path(result.file_path).unlink(missing_ok=True)
                except Exception:
                    pass
                source_label = "из папки" if is_from_folder else "из почты"
                set_error(f"Новая справка {source_label} отклонена: {reason} Сохранена предыдущая рабочая версия.")
                return None
            apply_loaded_state(tab, candidate_state)
            return result

    def _next_mail_autoupdate_at(from_dt: Optional[datetime] = None) -> datetime:
        base = from_dt or datetime.now(MOSCOW_TZ).replace(tzinfo=None)
        if base.tzinfo is not None:
            base = base.astimezone(MOSCOW_TZ).replace(tzinfo=None)
        candidate = base.replace(minute=20, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(hours=1)
        if candidate.hour < 6:
            candidate = candidate.replace(hour=6, minute=20, second=0, microsecond=0)
        elif candidate.hour > 23:
            candidate = (candidate + timedelta(days=1)).replace(hour=6, minute=20, second=0, microsecond=0)
        return candidate

    def _run_scheduled_mail_sync_once() -> dict[str, object]:
        # Автообновление не открывает весь почтовый архив: mail_service ищет только письма за последние сутки.
        if not get_selected_station_name():
            return {"updated": False, "skipped": True, "reason": "station_not_selected"}
        set_current_station_context()
        updated: list[str] = []
        errors: dict[str, str] = {}
        for tab in (TAB_APPROACH, TAB_DEPARTURE):
            try:
                result = try_mail_sync(tab, force=False)
                if result is not None:
                    updated.append(tab)
            except Exception as exc:
                # Плановое автообновление не должно вешать ошибку на экран пользователя.
                errors[tab] = str(exc)
        return {"updated": bool(updated), "tabs": updated, "errors": errors}

    def _mail_autoupdate_loop() -> None:
        while True:
            try:
                next_run = _next_mail_autoupdate_at()
                sleep_seconds = max(1.0, (next_run - datetime.now(MOSCOW_TZ).replace(tzinfo=None)).total_seconds())
                time.sleep(sleep_seconds)
                _run_scheduled_mail_sync_once()
            except Exception:
                time.sleep(60)

    def _start_mail_autoupdate_scheduler() -> None:
        if app.config.get("MAIL_AUTOUPDATE_STARTED"):
            return
        app.config["MAIL_AUTOUPDATE_STARTED"] = True
        thread = threading.Thread(target=_mail_autoupdate_loop, name="asu-podhod-mail-autoupdate", daemon=True)
        thread.start()

    def find_latest_local_source(source_tab: str) -> Optional[dict]:
        if source_tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return None

        candidates: list[dict] = []

        try:
            archive_index = prune_archive(load_archive_index())
            for item in archive_index.get(source_tab, []):
                if not isinstance(item, dict) or not _archive_item_matches_current_station(item):
                    continue
                file_path = Path(str(item.get("file_path") or ""))
                if not file_path.exists() or not file_path.is_file():
                    continue
                sort_dt = (
                    from_iso_datetime(item.get("saved_at"))
                    or from_iso_datetime(item.get("report_dt"))
                    or datetime.fromtimestamp(file_path.stat().st_mtime)
                )
                candidates.append(
                    {
                        "file_path": str(file_path),
                        "source_name": f"Архив: {item.get('source_name') or file_path.name}",
                        "source_kind": "archive",
                        "mail_signature": None,
                        "sort_dt": sort_dt,
                    }
                )
        except Exception:
            pass

        patterns = [f"{source_tab}_*.xlsx", f"{source_tab}_*.xls", f"{source_tab}_*.xlsm", f"{source_tab}_*.xltx", f"{source_tab}_*.xltm"]
        seen_paths: set[str] = set()
        local_mail_dir = _station_mail_dir()
        for pattern in patterns:
            for file_path in local_mail_dir.glob(pattern):
                try:
                    resolved = str(file_path.resolve())
                except Exception:
                    resolved = str(file_path)
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                if not file_path.exists() or not file_path.is_file():
                    continue
                try:
                    sort_dt = datetime.fromtimestamp(file_path.stat().st_mtime)
                except Exception:
                    sort_dt = now()
                candidates.append(
                    {
                        "file_path": str(file_path),
                        "source_name": f"Почта: {file_path.name}",
                        "source_kind": "mail",
                        "mail_signature": None,
                        "sort_dt": sort_dt,
                    }
                )

        if not candidates:
            return None
        candidates.sort(key=lambda item: item.get("sort_dt") or datetime.min, reverse=True)
        return candidates[0]

    def load_latest_local_source(source_tab: str) -> Optional[SourceState]:
        entry = find_latest_local_source(source_tab)
        if not entry:
            return None
        load_from_path(
            entry["file_path"],
            mode=source_tab,
            source_name=entry.get("source_name"),
            source_kind=str(entry.get("source_kind") or "file"),
            mail_signature=entry.get("mail_signature"),
        )
        return get_state(source_tab)

    def ensure_loaded(source_tab: str) -> Optional[SourceState]:
        state = get_state(source_tab)
        if state is not None:
            return state

        # Обычное открытие вкладок не должно обращаться к IMAP.
        # Почта проверяется только по ручной кнопке «Обновить»/«Почта»
        # и фоновым автообновлением по расписанию. Это убирает задержку
        # при каждом переходе в «Подход вагонов» и «Отправление вагонов».
        try:
            state = load_latest_local_source(source_tab)
            if state is not None:
                return state
        except Exception:
            pass
        if source_tab == TAB_APPROACH:
            default_path = app.config.get("DEFAULT_EXCEL")
            if default_path and Path(default_path).exists():
                load_from_path(default_path, mode=TAB_APPROACH, source_name=Path(default_path).name)
                return get_state(TAB_APPROACH)
        return None

    def get_effective_state(tab: str, archive_date: Optional[str]) -> Optional[SourceState]:
        source_tab = get_source_tab(tab)
        if archive_date:
            state = get_archived_state(source_tab, archive_date)
            if state is None:
                set_error("Архив за выбранную дату отсутствует")
            return state
        return ensure_loaded(source_tab)

    def get_display_state(tab: str, archive_date: Optional[str], idle_view: Optional[str] = None) -> Optional[SourceState]:
        station = set_current_station_context()
        if _station_bound_tab(tab) and not station:
            source_tab = get_station_idle_source_tab(get_idle_view(idle_view)) if tab == TAB_STATION_IDLE else get_source_tab(tab)
            return _empty_state_like(get_effective_state(source_tab, archive_date), source_tab)
        if tab == TAB_STATION_IDLE:
            source_tab = get_station_idle_source_tab(get_idle_view(idle_view))
            return _prepare_state_for_selected_station(tab, get_effective_state(source_tab, archive_date))
        source_tab = get_source_tab(tab)
        return _prepare_state_for_selected_station(tab, get_effective_state(source_tab, archive_date))

    def build_link(
        tab: str,
        road: Optional[str] = None,
        station: Optional[str] = None,
        kind: Optional[str] = None,
        cargo: Optional[str] = None,
        exact_wagon: Optional[str] = None,
        formed_trains: bool = False,
        destination: Optional[str] = None,
        origin: Optional[str] = None,
        train_index: Optional[str] = None,
        trip_start: Optional[str] = None,
        overdue_delivery: bool = False,
        primary_only: bool = False,
        idle_bucket: Optional[str] = None,
        idle_view: Optional[str] = None,
        loading_view: Optional[str] = None,
        archive_date: Optional[str] = None,
        exclude_ugleuralskaya: bool = False,
        raw_material_cargo: Optional[str] = None,
        raw_material_days: Optional[int] = None,
        cargo_name_filter: Optional[str] = None,
        trip_end_date: Optional[str] = None,
        departure_acceptance_date: Optional[str] = None,
    ) -> str:
        params = {"tab": tab}
        archive_date = archive_date if archive_date is not None else (request.args.get("archive_date") or "")
        if archive_date:
            params["archive_date"] = archive_date
        if road:
            params["road"] = road
        if station:
            params["station"] = station
        if kind and kind != "Всего":
            params["kind"] = kind
        if cargo and cargo in CARGO_ORDER:
            params["cargo"] = cargo
        if exact_wagon:
            params["wagon"] = exact_wagon
        if formed_trains:
            params["formed_trains"] = "1"
        if destination:
            params["destination"] = destination
        if origin:
            params["origin"] = origin
        if train_index:
            params["train_index"] = train_index
        if trip_start:
            params["trip_start"] = trip_start
        if overdue_delivery:
            params["overdue"] = "1"
        if primary_only:
            params["primary_only"] = "1"
        if idle_bucket:
            params["idle_bucket"] = idle_bucket
        if idle_view:
            params["idle_view"] = idle_view
        if loading_view:
            params["loading_view"] = loading_view
        if exclude_ugleuralskaya:
            params["exclude_ugleuralskaya"] = "1"
        if raw_material_cargo:
            params["raw_material_cargo"] = raw_material_cargo
        if raw_material_days is not None:
            params["raw_material_days"] = str(raw_material_days)
        if cargo_name_filter:
            params["cargo_name_filter"] = cargo_name_filter
        if trip_end_date:
            params["trip_end_date"] = trip_end_date
        if departure_acceptance_date:
            params["departure_acceptance_date"] = departure_acceptance_date
        if tab == TAB_APPROACH:
            approach_cargo_filter = normalize_spaces(request.args.get("approach_cargo_filter"))
            approach_previous_cargo_filter = normalize_spaces(request.args.get("approach_previous_cargo_filter"))
            if approach_cargo_filter:
                params["approach_cargo_filter"] = approach_cargo_filter
            if approach_previous_cargo_filter:
                params["approach_previous_cargo_filter"] = approach_previous_cargo_filter
        return url_for("details") + "?" + urlencode(params)

    def _notification_event_label(value: str) -> str:
        mapping = {
            "departure": "Отправление",
            "arrival": "Прибытие",
            "operation_changed": "Смена операции",
            "idle_started": "Начало простоя",
        }
        return mapping.get(str(value or ""), str(value or "").strip() or "Событие")

    def _notification_channel_label(value: str) -> str:
        mapping = {"app": "Внутри программы", "telegram": "Telegram", "whatsapp": "WhatsApp", "max": "MAX", "webhook": "Webhook"}
        return mapping.get(str(value or ""), str(value or "").strip() or "Канал")

    def load_notification_rules() -> list[dict]:
        payload = load_json_file(notification_rules_path, {"rules": []})
        items = payload.get("rules", []) if isinstance(payload, dict) else []
        cleaned: list[dict] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            cleaned.append({
                "id": str(item.get("id") or uuid.uuid4().hex),
                "name": normalize_spaces(item.get("name")) or "Без названия",
                "event_type": normalize_spaces(item.get("event_type")) or "operation_changed",
                "entity_type": normalize_spaces(item.get("entity_type")) or "wagon",
                "station_name": normalize_spaces(item.get("station_name")),
                "cargo_state": normalize_spaces(item.get("cargo_state")) or "all",
                "delivery_channel": normalize_spaces(item.get("delivery_channel")) or "app",
                "train_index": normalize_spaces(item.get("train_index")),
                "wagon_number": normalize_spaces(item.get("wagon_number")),
                "note": normalize_spaces(item.get("note")),
            })
        return cleaned

    def save_notification_rules(items: list[dict]) -> None:
        save_json_file(notification_rules_path, {"rules": items})

    def load_notification_channel() -> dict:
        payload = load_json_file(notification_channel_path, {})
        if not isinstance(payload, dict):
            payload = {}
        return {
            "channel_type": normalize_spaces(payload.get("channel_type")) or "app",
            "channel_target": str(payload.get("channel_target") or "").strip(),
            "channel_url": str(payload.get("channel_url") or "").strip(),
            "channel_comment": str(payload.get("channel_comment") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
            "telegram_target": str(payload.get("telegram_target") or "").strip(),
            "whatsapp_target": str(payload.get("whatsapp_target") or "").strip(),
            "max_target": str(payload.get("max_target") or "").strip(),
        }

    def save_notification_channel(payload: dict) -> None:
        save_json_file(notification_channel_path, payload)

    def _compose_ui_preferences(payload: dict) -> dict:
        if not isinstance(payload, dict):
            payload = {}
        accent_color = str(payload.get("accent_color") or "#2456d4").strip() or "#2456d4"
        font_color = str(payload.get("font_color") or "#182433").strip() or "#182433"
        return {
            "theme": normalize_spaces(payload.get("theme")).lower() or "light",
            "radius_style": normalize_spaces(payload.get("radius_style")).lower() or "soft",
            "density": normalize_spaces(payload.get("density")).lower() or "standard",
            "accent_color": accent_color,
            "accent_soft": _hex_to_rgba(accent_color, 0.12),
            "accent_border": _hex_to_rgba(accent_color, 0.24),
            "accent_focus": _hex_to_rgba(accent_color, 0.16),
            "font_color": font_color,
            "font_color_soft": _hex_to_rgba(font_color, 0.76),
            "default_map_view": normalize_spaces(payload.get("default_map_view")).lower() or "loaded",
            "dashboard_events_limit": max(3, min(20, int(payload.get("dashboard_events_limit") or 8))),
            "dashboard_show_map": bool(payload.get("dashboard_show_map", True)),
            "startup_tab": normalize_spaces(payload.get("startup_tab")).lower() or "dashboard",
            "dashboard_refresh_seconds": max(0, min(3600, int(payload.get("dashboard_refresh_seconds") or 0))),
        }

    def load_ui_preferences() -> dict:
        return _compose_ui_preferences(load_json_file(ui_preferences_path, {}))

    def save_ui_preferences(payload: dict) -> None:
        save_json_file(ui_preferences_path, _compose_ui_preferences(payload))

    def load_export_preferences() -> dict:
        payload = load_json_file(export_preferences_path, {})
        if not isinstance(payload, dict):
            payload = {}
        return {
            "excel_as_table": bool(payload.get("excel_as_table", True)),
            "excel_with_filters": bool(payload.get("excel_with_filters", True)),
            "excel_with_borders": bool(payload.get("excel_with_borders", True)),
            "excel_freeze_header": bool(payload.get("excel_freeze_header", True)),
            "excel_header_color": str(payload.get("excel_header_color") or "#dfeaff").strip() or "#dfeaff",
            "excel_header_font_color": str(payload.get("excel_header_font_color") or "#1f3352").strip() or "#1f3352",
        }

    def save_export_preferences(payload: dict) -> None:
        save_json_file(export_preferences_path, payload)

    app.config["UI_PREFERENCES"] = load_ui_preferences()
    app.config["EXPORT_PREFERENCES"] = load_export_preferences()

    def _build_dashboard_map_points(df: pd.DataFrame) -> tuple[list[dict], int]:
        points, unresolved = build_map_points(df)
        mapped: list[dict] = []
        for point in points:
            lat = float(point.get("latitude") or 0)
            lon = float(point.get("longitude") or 0)
            x = max(4.0, min(96.0, ((lon - 20.0) / 160.0) * 100.0))
            y = max(8.0, min(92.0, ((82.0 - lat) / 41.0) * 100.0))
            wagons = point.get("wagons", []) if isinstance(point.get("wagons"), list) else []
            kind = "loaded" if any(str(item.get("cargo_label") or "").startswith("Груж") for item in wagons) else "empty"
            mapped.append({
                "station_name": point.get("station_name") or "",
                "count": int(point.get("count") or len(wagons) or 0),
                "x": round(x, 2),
                "y": round(y, 2),
                "kind": kind,
            })
        mapped.sort(key=lambda item: (-item["count"], item["station_name"]))
        return mapped[:24], sum(int(item.get("count") or 0) for item in unresolved)

    def _calc_change(current: int, previous: Optional[int]) -> tuple[str, str]:
        if previous is None:
            # Для добавленных станций база сравнения может ещё не существовать;
            # для Углеуральской также не показываем пользователю служебную ошибку в карточке.
            # В этом случае просто не выводим процент изменения.
            return "—", "flat"
        if previous == 0:
            if current == 0:
                return "0%", "flat"
            return "+100%", "up"
        diff = ((current - previous) / previous) * 100.0
        label = f"{diff:+.1f}%"
        if abs(diff) < 0.05:
            return "0%", "flat"
        return label.replace(".0%", "%"), ("up" if diff > 0 else "down")

    def _latest_previous_archive_date(source_tab: str, current_state: Optional[SourceState]) -> Optional[str]:
        dates = list_archived_dates(source_tab)
        if not dates:
            return None
        current_label = current_state.report_dt.strftime("%Y-%m-%d") if current_state and current_state.report_dt else ""
        filtered = [item for item in dates if item and item != current_label]
        return filtered[-1] if filtered else None

    def _dashboard_links() -> list[dict]:
        return [
            {"title": "Подход вагонов", "sub": "", "href": url_for("index", tab=TAB_APPROACH)},
            {"title": "Отправление вагонов", "sub": "", "href": url_for("index", tab=TAB_DEPARTURE)},
            {"title": "Погрузка", "sub": "", "href": url_for("index", tab=TAB_LOADING)},
            {"title": "Простои", "sub": "", "href": url_for("index", tab=TAB_STATION_IDLE)},
            {"title": "Сырье", "sub": "", "href": url_for("index", tab=TAB_RAW_MATERIAL)},
            {"title": "Техническое состояние", "sub": "", "href": url_for("technical_state_index")},
            {"title": "Ручной фильтр", "sub": "", "href": url_for("index", tab=TAB_MANUAL)},
            {"title": "Архив", "sub": "", "href": url_for("archive_search")},
            {"title": "Авторассылка справок", "sub": "", "href": url_for("mailing_rules")},
            {"title": "Настройки", "sub": "", "href": url_for("settings_page")},
        ]

    def _build_dashboard_context() -> dict:
        ui_preferences = load_ui_preferences()
        app.config["UI_PREFERENCES"] = ui_preferences
        selected_station = set_current_station_context()
        if not selected_station:
            return {
                "title": APP_TITLE,
                "selected_station": "",
                "dashboard_metrics": [],
                "dashboard_map_points": [],
                "dashboard_map_missing_count": 0,
                "dashboard_events": [],
                "dashboard_links": _dashboard_links(),
                "station_options": get_station_options(),
                "dashboard_map_view": "loaded",
                "dashboard_refresh_seconds": int(ui_preferences.get("dashboard_refresh_seconds") or 0),
                "error_message": pop_error(),
                "success_message": pop_success(),
            }
        approach_state = get_display_state(TAB_APPROACH, "")
        departure_state = get_display_state(TAB_DEPARTURE, "")
        approach_df = filter_primary_destination(approach_state.df) if approach_state is not None else pd.DataFrame()
        approach_df = _positive_distance_df(approach_df) if approach_state is not None else pd.DataFrame()
        if "cargo_state" not in approach_df.columns and not approach_df.empty:
            approach_df["cargo_state"] = approach_df.get("Вес груза (кг)", pd.Series(index=approach_df.index)).map(lambda v: "гр" if (float(v) if str(v).strip().replace('.', '', 1).isdigit() else 0) > 0 else "пор")
        loaded_df = approach_df[approach_df.get("cargo_state", pd.Series(index=approach_df.index, dtype=object)) == "гр"].copy() if not approach_df.empty else pd.DataFrame()
        empty_df = approach_df[approach_df.get("cargo_state", pd.Series(index=approach_df.index, dtype=object)) == "пор"].copy() if not approach_df.empty else pd.DataFrame()

        prev_approach_date = _latest_previous_archive_date(TAB_APPROACH, approach_state)
        prev_approach = get_archived_state(TAB_APPROACH, prev_approach_date) if prev_approach_date else None
        prev_approach = _prepare_state_for_selected_station(TAB_APPROACH, prev_approach) if prev_approach is not None else None
        prev_df = filter_primary_destination(prev_approach.df) if prev_approach is not None else pd.DataFrame()
        prev_df = _positive_distance_df(prev_df) if prev_approach is not None else pd.DataFrame()
        if "cargo_state" not in prev_df.columns and not prev_df.empty:
            prev_df["cargo_state"] = prev_df.get("Вес груза (кг)", pd.Series(index=prev_df.index)).map(lambda v: "гр" if (float(v) if str(v).strip().replace('.', '', 1).isdigit() else 0) > 0 else "пор")
        prev_loaded = int((prev_df.get("cargo_state", pd.Series(index=prev_df.index, dtype=object)) == "гр").sum()) if not prev_df.empty else None
        prev_empty = int((prev_df.get("cargo_state", pd.Series(index=prev_df.index, dtype=object)) == "пор").sum()) if not prev_df.empty else None
        prev_overdue = int(len(filter_detail(prev_approach.df, overdue_delivery=True, report_dt=prev_approach.report_dt, primary_destination_only=True))) if prev_approach is not None else None

        prev_departure_date = _latest_previous_archive_date(TAB_DEPARTURE, departure_state)
        prev_departure = get_archived_state(TAB_DEPARTURE, prev_departure_date) if prev_departure_date else None
        prev_departure = _prepare_state_for_selected_station(TAB_DEPARTURE, prev_departure) if prev_departure is not None else None

        approach_today_date = moscow_today()
        approach_yesterday_date = approach_today_date - timedelta(days=1)
        departure_today_date = moscow_today()
        departure_yesterday_date = departure_today_date - timedelta(days=1)
        arrived_today = _count_trip_end_for_day(approach_state, approach_today_date, primary_destination_only=True) if approach_state is not None else 0
        arrived_yesterday = _count_trip_end_for_day(approach_state, approach_yesterday_date, primary_destination_only=True) if approach_state is not None and approach_yesterday_date is not None else None
        sent_today = _count_departure_acceptance_for_day(departure_state, departure_today_date) if departure_state is not None else 0
        sent_yesterday = _count_departure_acceptance_for_day(departure_state, departure_yesterday_date) if departure_state is not None and departure_yesterday_date is not None else None
        overdue = int(len(filter_detail(approach_state.df, overdue_delivery=True, report_dt=approach_state.report_dt, primary_destination_only=True))) if approach_state is not None else 0

        loaded_change = _calc_change(int(len(loaded_df)), prev_loaded)
        empty_change = _calc_change(int(len(empty_df)), prev_empty)
        total_prev = (prev_loaded or 0) + (prev_empty or 0) if prev_loaded is not None and prev_empty is not None else None
        total_change = _calc_change(int(len(approach_df)), total_prev)
        overdue_change = _calc_change(overdue, prev_overdue)
        arrived_change = _calc_change(arrived_today, arrived_yesterday)
        sent_change = _calc_change(sent_today, sent_yesterday)

        requested_map_view = normalize_spaces(request.args.get("map_view")).lower() or ui_preferences.get("default_map_view") or "loaded"
        map_view = requested_map_view if requested_map_view in {"loaded", "empty", "all"} else "loaded"
        map_df = loaded_df if map_view == "loaded" else empty_df if map_view == "empty" else approach_df
        dashboard_map_points, dashboard_map_missing_count = _build_dashboard_map_points(map_df)

        departure_focus = tuple(get_departure_direction_cards())
        approach_focus = tuple(get_approach_direction_cards())
        event_rows: list[dict] = []

        def _match_focus_station(value: object, focus_stations: tuple[str, ...]) -> str:
            station_value = normalize_spaces(value)
            station_upper = station_value.upper().replace("Ё", "Е")
            for target in focus_stations:
                normalized_target = target.upper().replace("Ё", "Е")
                if normalized_target in station_upper:
                    return target
            return ""

        def _format_event_rows_from_subset(subset: pd.DataFrame, limit: int = 8) -> None:
            if subset is None or subset.empty:
                return
            subset = subset.copy()
            subset["__event_dt"] = subset.get("Дата и время операции", pd.Series(index=subset.index)).map(parse_any_datetime)
            subset["__train"] = subset.get("Индекс поезда", pd.Series(index=subset.index)).map(lambda v: normalize_spaces(v) or "без индекса")
            subset["__operation"] = subset.get("Операция с вагоном", pd.Series(index=subset.index)).map(lambda v: strip_last_numeric_code(v) or "Операция")
            if "__station" not in subset.columns:
                subset["__station"] = selected_station
            grouped = (
                subset.groupby(["__station", "__train", "__operation", "Дата и время операции"], dropna=False)
                .size()
                .reset_index(name="count")
            )
            grouped["__event_dt"] = grouped["Дата и время операции"].map(parse_any_datetime)
            grouped = grouped.sort_values(by="__event_dt", ascending=False, na_position="last")
            for _, row in grouped.head(limit).iterrows():
                count = int(row.get("count") or 0)
                wagons_label = "вагон" if count == 1 else "вагона" if 1 < count < 5 else "вагонов"
                operation_label = str(row.get("__operation") or "Операция")
                event_dt_label = str(row.get("Дата и время операции") or "—")
                station_label = normalize_spaces(row.get("__station")) or selected_station
                event_rows.append({
                    "title": f"{station_label} {count} {wagons_label}",
                    "time": f"{operation_label} — {event_dt_label}",
                    "meta": f"({row['__train']})",
                    "sort_dt": row.get("__event_dt"),
                })

        def _collect_station_events(df: pd.DataFrame, station_columns: list[str], focus_stations: tuple[str, ...]) -> None:
            if df is None or df.empty:
                return
            station_values = pd.Series([""] * len(df), index=df.index, dtype=object)
            for station_column in station_columns:
                if station_column not in df.columns:
                    continue
                matched = df[station_column].map(lambda value: _match_focus_station(value, focus_stations))
                station_values = station_values.where(station_values.astype(str).str.len() > 0, matched)
            subset = df[station_values.astype(str).str.len() > 0].copy()
            if subset.empty:
                return
            subset["__station"] = station_values.loc[subset.index]
            _format_event_rows_from_subset(subset)

        def _collect_any_station_events(df: pd.DataFrame, station_columns: list[str]) -> None:
            if df is None or df.empty:
                return
            subset = df.copy()
            station_values = pd.Series([""] * len(subset), index=subset.index, dtype=object)
            for station_column in station_columns:
                if station_column not in subset.columns:
                    continue
                values = subset[station_column].map(normalize_spaces)
                station_values = station_values.where(station_values.astype(str).str.len() > 0, values)
            station_values = station_values.where(station_values.astype(str).str.len() > 0, selected_station)
            subset["__station"] = station_values
            _format_event_rows_from_subset(subset)

        if is_base_station(selected_station):
            if departure_state is not None:
                _collect_station_events(departure_state.df.copy(), ["Станция назначения"], departure_focus)
            if approach_state is not None:
                _collect_station_events(approach_state.df.copy(), ["Станция отправления"], approach_focus)
        else:
            # Для добавленных станций показываем любые последние события из комплекта справок выбранной станции.
            if departure_state is not None:
                _collect_any_station_events(departure_state.df.copy(), ["Станция назначения", "Станция операции", "Станция отправления"])
            if approach_state is not None:
                _collect_any_station_events(approach_state.df.copy(), ["Станция отправления", "Станция операции", "Станция назначения"])
        event_rows.sort(key=lambda item: item.get("sort_dt") or datetime.min, reverse=True)
        configured_events_limit = int(ui_preferences.get("dashboard_events_limit") or 8)
        effective_events_limit = max(configured_events_limit, 6)
        events = [{k:v for k,v in item.items() if k != "sort_dt"} for item in event_rows[: effective_events_limit]]

        links = _dashboard_links()

        metrics = []
        for label, value, change in [
            (f"Всего в пути на {selected_station}", int(len(approach_df)), total_change),
            ("Нарушен срок доставки", overdue, overdue_change),
            ("Гружёных в пути", int(len(loaded_df)), loaded_change),
            ("Порожних в пути", int(len(empty_df)), empty_change),
            ("Отправлено сегодня", sent_today, sent_change),
            ("Прибыло сегодня", arrived_today, arrived_change),
        ]:
            metrics.append({
                "label": label,
                "value": value,
                "trend_label": change[0],
                "trend_class": change[1],
            })

        return {
            "title": APP_TITLE,
            "selected_station": selected_station,
            "dashboard_metrics": metrics,
            "dashboard_map_points": dashboard_map_points if ui_preferences.get("dashboard_show_map", True) else [],
            "dashboard_map_missing_count": dashboard_map_missing_count if ui_preferences.get("dashboard_show_map", True) else 0,
            "dashboard_events": events,
            "dashboard_links": links,
            "station_options": get_station_options(),
            "dashboard_map_view": map_view,
            "dashboard_refresh_seconds": int(ui_preferences.get("dashboard_refresh_seconds") or 0),
            "error_message": pop_error(),
            "success_message": pop_success(),
        }

    def _build_settings_context() -> dict:
        ui_preferences = load_ui_preferences()
        export_preferences = load_export_preferences()
        app.config["UI_PREFERENCES"] = ui_preferences
        app.config["EXPORT_PREFERENCES"] = export_preferences
        rules = []
        for item in load_notification_rules():
            station_name = item.get("station_name") or "любая станция"
            cargo_state = item.get("cargo_state") or "all"
            cargo_label = "все вагоны" if cargo_state == "all" else "гружёные" if cargo_state == "гр" else "порожние"
            entity_label = "поезд" if item.get("entity_type") == "train" else "вагон"
            extra_parts = []
            if item.get("train_index"):
                extra_parts.append(f"индекс {item.get('train_index')}")
            if item.get("wagon_number"):
                extra_parts.append(f"вагон {item.get('wagon_number')}")
            base_label = f"{entity_label}, {station_name}, {cargo_label}"
            if extra_parts:
                base_label += "; " + ", ".join(extra_parts)
            rules.append({
                **item,
                "event_label": _notification_event_label(str(item.get("event_type") or "")),
                "channel_label": _notification_channel_label(str(item.get("delivery_channel") or "")),
                "condition_label": base_label,
            })
        return {
            "title": APP_TITLE,
            "current_tab": TAB_SETTINGS,
            "current_tab_label": EXTRA_TAB_LABELS[TAB_SETTINGS],
            "notification_rules": rules,
            "notification_channel": load_notification_channel(),
            "ui_preferences": ui_preferences,
            "export_preferences": export_preferences,
            "station_sources": load_station_sources(),
            "base_station_name": DEFAULT_WORK_STATION,
            "approach_default_direction_cards": list(APPROACH_ORIGIN_CARDS),
            "departure_default_direction_cards": list(DEPARTURE_DESTINATION_CARDS),
            "imap_username": normalize_spaces((app.config.get("SETTINGS") or {}).get("imap", {}).get("username")) or normalize_spaces(get_imap_config(app.config.get("SETTINGS", {}), TAB_APPROACH).get("username")),
            "error_message": pop_error(),
            "success_message": pop_success(),
        }

    def common_index_context(tab: str, state: Optional[SourceState], rows: list[dict], extra: dict) -> dict:
        license_ctx = get_license_snapshot()
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        return {
            "title": APP_TITLE,
            "app_title": APP_TITLE,
            "current_tab": tab,
            "current_tab_label": _dynamic_tab_label(tab, TAB_LABELS.get(tab, EXTRA_TAB_LABELS.get(tab, tab))),
            "selected_station": get_selected_station_name(),
            "destination_keyword": (get_selected_station_name() or DESTINATION_KEYWORD.title()),
            "rows": rows,
            "source_name": state.source_name if state else "Файл ещё не загружен",
            "source_time": state.loaded_at.strftime("Обновлено %d.%m.%Y %H:%M:%S") if state else "",
            "report_date_label": state.report_dt.strftime("%d.%m.%Y %H:%M") if state and state.report_dt else "",
            "search_value": request.args.get("wagon", ""),
            "sample_available": bool(app.config.get("DEFAULT_EXCEL")),
            "has_last_path": bool(state and state.file_path and not archive_date),
            "network_hint": app.config.get("LAN_URL") if app.config.get("HOST_MODE") != "127.0.0.1" else "",
            "error_message": pop_error(),
            "success_message": pop_success(),
            "archive_date": archive_date,
            "allow_archive": tab in {TAB_APPROACH, TAB_DEPARTURE, TAB_STATION_IDLE, TAB_RAW_MATERIAL},
            "allow_upload": not archive_date,
            "upload_tab": get_station_idle_source_tab(idle_view) if tab == TAB_STATION_IDLE else get_source_tab(tab),
            "show_stop_rent_button": tab in {TAB_APPROACH, TAB_DEPARTURE},
            "station_idle_mode": idle_view,
            "loading_mode": get_loading_view(request.args.get("loading_view")),
            "selected_month": normalize_month_key(request.args.get("loading_month"), state.report_dt if state and state.report_dt else now()),
            "approach_cargo_filter_options": [],
            "approach_previous_cargo_filter_options": [],
            "approach_cargo_filter_value": normalize_spaces(request.args.get("approach_cargo_filter")),
            "approach_previous_cargo_filter_value": normalize_spaces(request.args.get("approach_previous_cargo_filter")),
            **license_ctx,
            **extra,
        }


    def _manual_saved_filters() -> list[dict]:
        payload = load_json_file(manual_filters_path, {"filters": []})
        items = payload.get("filters", []) if isinstance(payload, dict) else []
        cleaned: list[dict] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            source_key = str(item.get("source_key") or "approach").strip()
            criteria = item.get("criteria") if isinstance(item.get("criteria"), dict) else {}
            cleaned.append({
                "name": name,
                "source_key": source_key,
                "criteria": criteria,
                "saved_at": str(item.get("saved_at") or ""),
            })
        cleaned.sort(key=lambda value: str(value.get("name") or "").lower())
        return cleaned

    def _save_manual_saved_filters(items: list[dict]) -> None:
        save_json_file(manual_filters_path, {"filters": items})

    def _manual_saved_filter_map() -> dict[str, dict]:
        return {str(item.get("name") or ""): item for item in _manual_saved_filters()}

    _MANUAL_MAILING_REPORT_PREFIX = "manual_saved:"

    def _make_manual_mailing_report_type(filter_name: str) -> str:
        return f"{_MANUAL_MAILING_REPORT_PREFIX}{_normalize_manual_text(filter_name)}"

    def _parse_manual_mailing_report_name(report_type: object) -> str:
        text_value = _normalize_manual_text(report_type)
        if text_value.startswith(_MANUAL_MAILING_REPORT_PREFIX):
            return text_value[len(_MANUAL_MAILING_REPORT_PREFIX):].strip()
        return ""

    def _manual_mailing_label(filter_name: str) -> str:
        return f"Ручной фильтр: {_normalize_manual_text(filter_name)}"

    def _manual_source_options() -> list[dict]:
        return [
            {"value": "approach", "label": "Подход вагонов"},
            {"value": "departure", "label": "Отправление вагонов"},
            {"value": "idle_ugleuralskaya", "label": f"Простой на станции {get_selected_station_name() or DEFAULT_WORK_STATION}"},
            {"value": "idle_destination", "label": "Простой на станции назначения"},
            {"value": "raw_material", "label": "Сырье"},
            {"value": "loading_today", "label": "Погрузка сегодня"},
            {"value": "loading_yesterday", "label": "Погрузка вчера"},
            {"value": "loading_pending", "label": "Погружены, но не отправлены"},
        ]

    def _manual_source_labels() -> dict[str, str]:
        return {item["value"]: item["label"] for item in _manual_source_options()}

    def _normalize_manual_text(value: object) -> str:
        return str(value or "").strip()

    def _manual_extract_series(df: pd.DataFrame, columns: list[str]) -> pd.Series:
        if df is None or df.empty:
            return pd.Series(dtype=str)
        available = [column for column in columns if column in df.columns]
        if not available:
            return pd.Series(["" for _ in range(len(df))], index=df.index, dtype=object)
        result = pd.Series(["" for _ in range(len(df))], index=df.index, dtype=object)
        for column in available:
            values = df[column].fillna("").astype(str).str.strip()
            mask = (result == "") & (values != "")
            result.loc[mask] = values.loc[mask]
        return result

    def _manual_extract_date_series(df: pd.DataFrame, columns: list[str]) -> pd.Series:
        series = _manual_extract_series(df, columns)
        return series.map(parse_any_date)

    def _manual_parse_input_date(value: object) -> Optional[date]:
        text_value = _normalize_manual_text(value)
        if not text_value:
            return None
        try:
            return date.fromisoformat(text_value)
        except Exception:
            return None

    def _manual_unique_values(df: pd.DataFrame, columns: list[str]) -> list[str]:
        if df is None or df.empty:
            return []
        series = _manual_extract_series(df, columns)
        values = sorted({str(value).strip() for value in series.tolist() if str(value).strip()}, key=lambda item: item.lower())
        return values

    def _manual_cargo_state_label(value: object) -> str:
        text_value = _normalize_manual_text(value).lower()
        if not text_value:
            return ""
        if "пор" in text_value:
            return "Порожние"
        if "гр" in text_value or "груж" in text_value:
            return "Груженые"
        return _normalize_manual_text(value)

    def _manual_source_payload(source_key: str, archive_date: str) -> tuple[Optional[SourceState], pd.DataFrame, str, Optional[str]]:
        labels = _manual_source_labels()
        label = labels.get(source_key, labels.get("approach") or "Подход вагонов")
        try:
            if source_key == "departure":
                state = get_effective_state(TAB_DEPARTURE, archive_date)
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                return state, filter_detail(state.df, report_dt=state.report_dt), label, None
            if source_key == "idle_ugleuralskaya":
                state = get_display_state(TAB_STATION_IDLE, archive_date, "ugleuralskaya")
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                return state, filter_detail(state.df, report_dt=state.report_dt, idle_mode="ugleuralskaya"), label, None
            if source_key == "idle_destination":
                state = get_display_state(TAB_STATION_IDLE, archive_date, "destination")
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                return state, filter_detail(state.df, report_dt=state.report_dt, idle_mode="destination"), label, None
            if source_key == "raw_material":
                state = get_effective_state(TAB_RAW_MATERIAL, archive_date)
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                raw_df = filter_raw_material_idle(state.df, state.report_dt)
                return state, filter_detail(raw_df, report_dt=state.report_dt), label, None
            if source_key == "loading_today":
                state = get_effective_state(TAB_DEPARTURE, archive_date)
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                loading_df = filter_loading_view(state.df, state.report_dt, "today")
                return state, filter_detail(loading_df, report_dt=state.report_dt), label, None
            if source_key == "loading_yesterday":
                state = get_effective_state(TAB_DEPARTURE, archive_date)
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                loading_df = filter_loading_view(state.df, state.report_dt, "yesterday")
                return state, filter_detail(loading_df, report_dt=state.report_dt), label, None
            if source_key == "loading_pending":
                state = get_effective_state(TAB_DEPARTURE, archive_date)
                if state is None:
                    return None, pd.DataFrame(), label, "Источник данных не загружен."
                loading_df = filter_loading_view(state.df, state.report_dt, "pending")
                return state, filter_detail(loading_df, report_dt=state.report_dt), label, None
            state = get_effective_state(TAB_APPROACH, archive_date)
            if state is None:
                return None, pd.DataFrame(), label, "Источник данных не загружен."
            return state, filter_detail(state.df, report_dt=state.report_dt), labels.get("approach") or label, None
        except Exception as exc:
            return None, pd.DataFrame(), label, str(exc)

    def _manual_field_value(field: dict, saved_criteria: Optional[dict] = None, prefer_saved: bool = False) -> object:
        saved_criteria = saved_criteria or {}
        if field["kind"] == "multi":
            current_values = [item for item in request.args.getlist(field["param"]) if item]
            saved_values = saved_criteria.get(field["param"])
            saved_values = saved_values if isinstance(saved_values, list) else []
            if prefer_saved and saved_values:
                return saved_values
            if current_values:
                return current_values
            return saved_values
        current_value = _normalize_manual_text(request.args.get(field["param"], ""))
        saved_value = _normalize_manual_text(saved_criteria.get(field["param"]))
        if prefer_saved and saved_value:
            return saved_value
        if field["param"] in request.args:
            return current_value
        if current_value:
            return current_value
        return saved_value

    def _manual_filter_definitions(df: pd.DataFrame, saved_criteria: Optional[dict] = None, prefer_saved: bool = False) -> list[dict]:
        saved_criteria = saved_criteria or {}
        fields = [
            {"key": "kind", "param": "kind", "label": "Род подвижного состава", "kind": "multi", "columns": ["Род вагона", "raw_kind", "raw_kind_display"], "size": 6},
            {"key": "cargo_state", "param": "cargo_state", "label": "Состояние вагона", "kind": "single", "options": ["Все", "Груженые", "Порожние"]},
            {"key": "trip_start_from", "param": "trip_start_from", "label": "Дата начала рейса: от", "kind": "date", "columns": ["trip_start_time", "Дата и время начала рейса"]},
            {"key": "trip_start_to", "param": "trip_start_to", "label": "Дата начала рейса: до", "kind": "date", "columns": ["trip_start_time", "Дата и время начала рейса"]},
            {"key": "operation_date_from", "param": "operation_date_from", "label": "Дата операции: от", "kind": "date", "columns": ["Дата и время операции", "operation_time"]},
            {"key": "operation_date_to", "param": "operation_date_to", "label": "Дата операции: до", "kind": "date", "columns": ["Дата и время операции", "operation_time"]},
            {"key": "owner", "param": "owner", "label": "Собственник", "kind": "text", "columns": ["owner_display", "Собственник"], "placeholder": "Начните вводить собственника"},
            {"key": "cargo_name", "param": "cargo_name", "label": "Груз", "kind": "text", "columns": ["cargo_name_display", "Наименование груза", "Груз"], "placeholder": "Начните вводить груз"},
            {"key": "shipper", "param": "shipper", "label": "Грузоотправитель", "kind": "text", "columns": ["Грузоотправитель"], "placeholder": "Начните вводить грузоотправителя"},
            {"key": "consignee", "param": "consignee", "label": "Грузополучатель", "kind": "text", "columns": ["Грузополучатель"], "placeholder": "Начните вводить грузополучателя"},
            {"key": "origin_road", "param": "origin_road", "label": "Дорога отправления", "kind": "text", "columns": ["origin_road_display", "Дорога отправления"], "placeholder": "Начните вводить дорогу отправления"},
            {"key": "destination_road", "param": "destination_road", "label": "Дорога назначения", "kind": "text", "columns": ["destination_road_display", "Дорога назначения"], "placeholder": "Начните вводить дорогу назначения"},
            {"key": "origin_station", "param": "origin_station", "label": "Станция отправления", "kind": "text", "columns": ["origin_station_display", "Станция отправления"], "placeholder": "Начните вводить станцию отправления"},
            {"key": "destination", "param": "destination", "label": "Станция назначения", "kind": "text", "columns": ["destination_display", "Станция назначения"], "placeholder": "Начните вводить станцию назначения"},
            {"key": "station", "param": "station", "label": "Станция операции", "kind": "text", "columns": ["station_display", "Станция операции"], "placeholder": "Начните вводить станцию операции"},
            {"key": "wagon_number", "param": "wagon_number", "label": "Номер вагона", "kind": "text", "columns": ["Номер вагона", "wagon_number"], "placeholder": "Введите номер вагона"},
        ]
        result: list[dict] = []
        for field in fields:
            field = dict(field)
            if field["kind"] == "multi":
                field["options"] = ["Все"] + _manual_unique_values(df, field.get("columns", []))
                field["selected"] = _manual_field_value(field, saved_criteria, prefer_saved)
                field["enabled"] = True
            elif field["kind"] == "single":
                field["value"] = _manual_field_value(field, saved_criteria, prefer_saved) or "Все"
                field["enabled"] = True
            elif field["kind"] == "date":
                field["value"] = _manual_field_value(field, saved_criteria, prefer_saved)
                field["enabled"] = True
            else:
                field["options"] = _manual_unique_values(df, field.get("columns", []))
                field["value"] = _manual_field_value(field, saved_criteria, prefer_saved)
                field["enabled"] = True
                field["datalist_id"] = f"manual-{field['key']}-list"
            result.append(field)
        return result

    def _apply_manual_filters(df: pd.DataFrame, fields: list[dict]) -> tuple[pd.DataFrame, list[dict[str, str]]]:
        if df is None or df.empty:
            return pd.DataFrame(), []
        filtered = df.copy()
        active_filters: list[dict[str, str]] = []
        for field in fields:
            if not field.get("enabled"):
                continue
            if field["kind"] == "multi":
                selected = [item for item in field.get("selected", []) if item and item != "Все"]
                if not selected:
                    continue
                values = _manual_extract_series(filtered, field.get("columns", []))
                filtered = filtered[values.isin(selected)].copy()
                for selected_item in selected:
                    active_filters.append({"param": field["param"], "value": selected_item, "text": f"{field['label']}: {selected_item}"})
                continue
            if field["kind"] == "date":
                value = _normalize_manual_text(field.get("value"))
                bound = _manual_parse_input_date(value)
                if bound is None:
                    continue
                series = _manual_extract_date_series(filtered, field.get("columns", []))
                if field["param"].endswith("_from"):
                    filtered = filtered[series >= bound].copy()
                else:
                    filtered = filtered[series <= bound].copy()
                active_filters.append({"param": field["param"], "value": value, "text": f"{field['label']}: {bound.strftime('%d.%m.%Y')}"})
                continue
            if field["key"] == "cargo_state":
                selected_value = _normalize_manual_text(field.get("value"))
                if not selected_value or selected_value == "Все":
                    continue
                labels = _manual_extract_series(filtered, ["cargo_state", "Сост. вагона", "wagon_state"]).map(_manual_cargo_state_label)
                filtered = filtered[labels == selected_value].copy()
                active_filters.append({"param": field["param"], "value": selected_value, "text": f"{field['label']}: {selected_value}"})
                continue
            value = _normalize_manual_text(field.get("value"))
            if not value:
                continue
            series = _manual_extract_series(filtered, field.get("columns", [])).str.lower()
            filtered = filtered[series.str.contains(value.lower(), na=False)].copy()
            active_filters.append({"param": field["param"], "value": value, "text": f"{field['label']}: {value}"})
        return filtered.reset_index(drop=True), active_filters

    def _manual_result_records(df: pd.DataFrame) -> list[dict[str, str]]:
        if df is None or df.empty:
            return []
        records: list[dict[str, str]] = []
        for _, row in df.iterrows():
            cargo_state = _manual_cargo_state_label(row.get("cargo_state", row.get("wagon_state", row.get("Сост. вагона", ""))))
            records.append({
                "wagon_number": _normalize_manual_text(row.get("Номер вагона", row.get("wagon_number", ""))),
                "raw_kind": _normalize_manual_text(row.get("Род вагона", row.get("raw_kind", ""))),
                "cargo_state": cargo_state,
                "owner": _normalize_manual_text(row.get("owner_display", row.get("Собственник", ""))),
                "cargo_name": _normalize_manual_text(row.get("cargo_name_display", row.get("Наименование груза", row.get("Груз", "")))),
                "shipper": _normalize_manual_text(row.get("Грузоотправитель", "")),
                "consignee": _normalize_manual_text(row.get("Грузополучатель", "")),
                "origin_station": _normalize_manual_text(row.get("origin_station_display", row.get("Станция отправления", ""))),
                "origin_road": _normalize_manual_text(row.get("origin_road_display", row.get("Дорога отправления", ""))),
                "destination": _normalize_manual_text(row.get("destination_display", row.get("Станция назначения", ""))),
                "destination_road": _normalize_manual_text(row.get("destination_road_display", row.get("Дорога назначения", ""))),
                "station": _normalize_manual_text(row.get("station_display", row.get("Станция операции", ""))),
                "road": _normalize_manual_text(row.get("road_display", row.get("Дорога операции", ""))),
                "operation": _normalize_manual_text(row.get("Операция с вагоном", row.get("operation", ""))),
                "operation_time": _normalize_manual_text(row.get("Дата и время операции", row.get("operation_time", ""))),
                "trip_end": _normalize_manual_text(row.get("Дата и время окончания рейса", row.get("trip_end", ""))),
            })
        return records

    def _manual_counts(df: pd.DataFrame) -> tuple[int, int, int]:
        if df is None or df.empty:
            return 0, 0, 0
        labels = _manual_extract_series(df, ["cargo_state", "Сост. вагона", "wagon_state"]).map(_manual_cargo_state_label)
        loaded = int((labels == "Груженые").sum())
        empty = int((labels == "Порожние").sum())
        return int(len(df.index)), loaded, empty

    def _manual_query_pairs_from_fields(
        selected_source: str,
        archive_date: str,
        selected_saved_filter: str,
        fields: list[dict],
        *,
        exclude_param: Optional[str] = None,
        exclude_value: Optional[str] = None,
        drop_saved_filter: bool = False,
    ) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [("tab", TAB_MANUAL), ("manual_source", selected_source or "approach")]
        if archive_date:
            params.append(("archive_date", archive_date))
        if selected_saved_filter and not drop_saved_filter:
            params.append(("saved_filter", selected_saved_filter))
        skipped_specific = False
        exclude_value_clean = _normalize_manual_text(exclude_value)
        for field in fields:
            if not field.get("enabled"):
                continue
            if field["kind"] == "multi":
                values = [item for item in field.get("selected", []) if _normalize_manual_text(item) and item != "Все"]
                for value in values:
                    if exclude_param == field["param"] and exclude_value_clean:
                        if (not skipped_specific) and _normalize_manual_text(value) == exclude_value_clean:
                            skipped_specific = True
                            continue
                    params.append((field["param"], _normalize_manual_text(value)))
                continue
            value = _normalize_manual_text(field.get("value"))
            if not value or (field["kind"] == "single" and value == "Все"):
                continue
            if exclude_param == field["param"]:
                if not exclude_value_clean or value == exclude_value_clean:
                    continue
            params.append((field["param"], value))
        return params

    def _manual_active_filter_items(
        selected_source: str,
        archive_date: str,
        selected_saved_filter: str,
        active_filters: list[dict[str, str]],
        fields: list[dict],
        source_label: str,
    ) -> list[dict[str, str]]:
        items: list[dict[str, str]] = [{"text": f"Источник: {source_label}", "remove_url": ""}]
        for item in active_filters:
            remove_url = url_for("index") + "?" + urlencode(
                _manual_query_pairs_from_fields(
                    selected_source,
                    archive_date,
                    selected_saved_filter,
                    fields,
                    exclude_param=item.get("param"),
                    exclude_value=item.get("value"),
                    drop_saved_filter=True,
                ),
                doseq=True,
            )
            items.append({"text": str(item.get("text") or ""), "remove_url": remove_url})
        return items

    def _manual_export_filename(selected_source: str, selected_saved_filter: str) -> str:
        base_name = _normalize_manual_text(selected_saved_filter) or f"Ручной фильтр_{_manual_source_labels().get(selected_source, selected_source)}"
        stamp = now().strftime("%Y-%m-%d_%H-%M")
        return f"{base_name}_{stamp}.xlsx"

    def _manual_redirect_url(form_data) -> str:
        params: list[tuple[str, str]] = [("tab", TAB_MANUAL)]
        archive_date = _normalize_manual_text(form_data.get("archive_date"))
        if archive_date:
            params.append(("archive_date", archive_date))
        selected_source = _normalize_manual_text(form_data.get("manual_source")) or "approach"
        params.append(("manual_source", selected_source))
        selected_saved = _normalize_manual_text(form_data.get("saved_filter"))
        if selected_saved:
            params.append(("saved_filter", selected_saved))
        for key in form_data.keys():
            if key in {"tab", "archive_date", "manual_source", "saved_filter", "manual_filter_name", "load_saved"}:
                continue
            values = form_data.getlist(key)
            for value in values:
                clean = _normalize_manual_text(value)
                if clean:
                    params.append((key, clean))
        return url_for("index") + "?" + urlencode(params, doseq=True)

    def build_manual_filter_context() -> dict:
        archive_date = request.args.get("archive_date", "")
        source_options = _manual_source_options()
        source_labels = _manual_source_labels()
        saved_filters = _manual_saved_filters()
        selected_saved_filter = _normalize_manual_text(request.args.get("saved_filter"))
        load_saved = _normalize_manual_text(request.args.get("load_saved")) == "1"
        saved_criteria: dict = {}
        selected_source = _normalize_manual_text(request.args.get("manual_source")) or "approach"
        if load_saved and selected_saved_filter:
            saved_item = _manual_saved_filter_map().get(selected_saved_filter)
            if saved_item:
                saved_criteria = saved_item.get("criteria") if isinstance(saved_item.get("criteria"), dict) else {}
                selected_source = _normalize_manual_text(saved_item.get("source_key")) or selected_source
        state, source_df, source_label, manual_message = _manual_source_payload(selected_source, archive_date)
        fields = _manual_filter_definitions(source_df, saved_criteria, load_saved)
        filtered_df, active_filters = _apply_manual_filters(source_df, fields)
        total_count, loaded_count, empty_count = _manual_counts(filtered_df)
        active_filter_items = _manual_active_filter_items(
            selected_source,
            archive_date,
            selected_saved_filter,
            active_filters,
            fields,
            source_labels.get(selected_source, source_label),
        )
        export_url = url_for("manual_filter_export") + "?" + urlencode(
            _manual_query_pairs_from_fields(
                selected_source,
                archive_date,
                selected_saved_filter,
                fields,
                drop_saved_filter=True,
            ),
            doseq=True,
        )
        return {
            "title": f"{APP_TITLE} — Ручной фильтр",
            "app_title": APP_TITLE,
            "current_tab": TAB_MANUAL,
            "error_message": pop_error(),
            "success_message": pop_success(),
            "manual_message": manual_message,
            "archive_date": archive_date,
            "manual_source_options": source_options,
            "manual_source_label": source_labels.get(selected_source, source_label),
            "selected_source": selected_source,
            "manual_fields": fields,
            "manual_records": _manual_result_records(filtered_df),
            "manual_active_filters": active_filter_items,
            "manual_total_count": total_count,
            "manual_export_url": export_url,
            "manual_loaded_count": loaded_count,
            "manual_empty_count": empty_count,
            "manual_saved_filters": saved_filters,
            "selected_saved_filter": selected_saved_filter,
            "manual_filter_name": selected_saved_filter,
            "source_name": state.source_name if state else "Источник данных ещё не загружен",
            "source_time": state.loaded_at.strftime("Обновлено %d.%m.%Y %H:%M:%S") if state else "",
            "report_date_label": state.report_dt.strftime("%d.%m.%Y %H:%M") if state and state.report_dt else "",
        }


    def _mailing_report_options() -> list[dict]:
        options = [
            {"value": "approach", "label": "Подход вагонов"},
            {"value": "departure", "label": "Отправление вагонов"},
            {"value": "idle_ugleuralskaya", "label": f"Простой на станции {get_selected_station_name() or DEFAULT_WORK_STATION}"},
            {"value": "idle_destination", "label": "Простой на станции назначения"},
            {"value": "raw_material", "label": "Сырье"},
            {"value": "loading_today", "label": "Погрузка сегодня"},
            {"value": "loading_yesterday", "label": "Погрузка вчера"},
            {"value": "loading_pending", "label": "Погружены, но не отправлены более суток"},
        ]
        for saved_item in _manual_saved_filters():
            filter_name = _normalize_manual_text(saved_item.get("name"))
            if not filter_name:
                continue
            options.append(
                {
                    "value": _make_manual_mailing_report_type(filter_name),
                    "label": _manual_mailing_label(filter_name),
                }
            )
        return options

    def _mailing_report_labels() -> dict[str, str]:
        labels = {item["value"]: item["label"] for item in _mailing_report_options()}
        for rule in mailing_storage.list_rules():
            filter_name = _parse_manual_mailing_report_name(getattr(rule, "report_type", "")) or _normalize_manual_text(getattr(rule, "manual_filter_name", ""))
            if filter_name:
                labels[_make_manual_mailing_report_type(filter_name)] = _manual_mailing_label(filter_name)
        return labels

    def _mailing_weekday_options() -> list[dict]:
        return [
            {"value": 0, "label": "ПН"},
            {"value": 1, "label": "ВТ"},
            {"value": 2, "label": "СР"},
            {"value": 3, "label": "ЧТ"},
            {"value": 4, "label": "ПТ"},
            {"value": 5, "label": "СБ"},
            {"value": 6, "label": "ВС"},
        ]

    def _mailing_schedule_options() -> list[dict]:
        return [
            {"value": MailingScheduleType.DAILY.value, "label": "Ежедневно"},
            {"value": MailingScheduleType.WEEKDAYS.value, "label": "По будням"},
            {"value": MailingScheduleType.SELECTED_WEEKDAYS.value, "label": "По выбранным дням недели"},
            {"value": MailingScheduleType.MULTIPLE_TIMES_DAILY.value, "label": "Несколько раз в день"},
        ]

    def _split_address_list(raw_value: str) -> str:
        text = str(raw_value or "")
        for separator in ["\\r", "\\n", ";", ","]:
            text = text.replace(separator, ";")
        parts = [part.strip() for part in text.split(";") if part.strip()]
        return "; ".join(parts)

    def _parse_times_value(raw_value: str) -> list[str]:
        text = str(raw_value or "")
        for separator in ["\\r", "\\n", ";"]:
            text = text.replace(separator, ",")
        parts = [part.strip() for part in text.split(",") if part.strip()]
        clean: list[str] = []
        for part in parts:
            value = part
            if len(value) == 4 and value[1] == ":":
                value = f"0{value}"
            if len(value) != 5 or value[2] != ":":
                continue
            hour, minute = value.split(":", 1)
            if not hour.isdigit() or not minute.isdigit():
                continue
            hh = int(hour)
            mm = int(minute)
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                clean.append(f"{hh:02d}:{mm:02d}")
        return sorted(set(clean))

    def _mailing_form_rule(rule: Optional[MailingRule] = None) -> MailingRule:
        base_rule = rule or MailingRule()
        report_labels = _mailing_report_labels()
        report_type = (request.form.get("report_type") or base_rule.report_type or "approach").strip()
        if report_type not in report_labels:
            report_type = base_rule.report_type if base_rule.report_type in report_labels else "approach"
        schedule_type = (request.form.get("schedule_type") or base_rule.schedule_type or MailingScheduleType.DAILY.value).strip()
        schedule_values = {item["value"] for item in _mailing_schedule_options()}
        if schedule_type not in schedule_values:
            schedule_type = MailingScheduleType.DAILY.value
        raw_weekdays = request.form.getlist("weekdays")
        weekdays: list[int] = []
        for value in raw_weekdays:
            text_value = str(value or "").strip()
            if text_value.isdigit():
                weekdays.append(int(text_value))
        times = _parse_times_value(request.form.get("times") or ", ".join(base_rule.normalized_times()))
        manual_filter_name = _parse_manual_mailing_report_name(report_type)
        return MailingRule(
            id=base_rule.id,
            enabled=(request.form.get("enabled") in {"1", "true", "True", "on"}) if request.method == "POST" else base_rule.enabled,
            name=(request.form.get("name") or base_rule.name).strip(),
            report_type=report_type,
            manual_filter_name=manual_filter_name,
            to=_split_address_list(request.form.get("to") or base_rule.to),
            cc=_split_address_list(request.form.get("cc") or base_rule.cc),
            bcc=_split_address_list(request.form.get("bcc") or base_rule.bcc),
            subject=(request.form.get("subject") or base_rule.subject).strip(),
            body=request.form.get("body") if request.method == "POST" else base_rule.body,
            schedule_type=schedule_type,
            weekdays=weekdays if request.method == "POST" else base_rule.normalized_weekdays(),
            times=times if request.method == "POST" else base_rule.normalized_times(),
            attach_filename_template=(request.form.get("attach_filename_template") or base_rule.attach_filename_template or "{report_label}_{date}.xlsx").strip(),
            add_datetime_to_subject=(request.form.get("add_datetime_to_subject") in {"1", "true", "True", "on"}) if request.method == "POST" else base_rule.add_datetime_to_subject,
            last_run_at=base_rule.last_run_at,
            last_slot_key=base_rule.last_slot_key,
            last_status=base_rule.last_status,
            last_error=base_rule.last_error,
            created_at=base_rule.created_at,
            updated_at=base_rule.updated_at,
        )

    def _validate_mailing_rule(rule: MailingRule) -> Optional[str]:
        if not rule.name:
            return "Не указано название рассылки."
        if rule.report_type not in _mailing_report_labels():
            return "Выбран неизвестный тип справки."
        manual_filter_name = _parse_manual_mailing_report_name(rule.report_type)
        if manual_filter_name and manual_filter_name not in _manual_saved_filter_map():
            return f'Сохранённый ручной фильтр «{manual_filter_name}» не найден.'
        if not rule.to:
            return "Не указаны получатели."
        if not rule.normalized_times():
            return "Не указано корректное время отправки."
        if rule.schedule_type == MailingScheduleType.SELECTED_WEEKDAYS.value and not rule.normalized_weekdays():
            return "Для выбранного режима нужно указать хотя бы один день недели."
        if not rule.attach_filename_template:
            return "Не указан шаблон имени вложения."
        return None

    def _build_workbook_bytes(summary_df: pd.DataFrame, detail_df: pd.DataFrame) -> bytes:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                temp_path = Path(tmp.name)
            write_excel_report(summary_df, detail_df, str(temp_path))
            return temp_path.read_bytes()
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def _build_manual_saved_filter_report_bytes(filter_name: str) -> bytes:
        filter_name = _normalize_manual_text(filter_name)
        saved_item = _manual_saved_filter_map().get(filter_name)
        if saved_item is None:
            raise ValueError(f'Сохранённый ручной фильтр «{filter_name}» не найден.')
        source_key = _normalize_manual_text(saved_item.get("source_key")) or "approach"
        criteria = saved_item.get("criteria") if isinstance(saved_item.get("criteria"), dict) else {}
        _state, source_df, _source_label, manual_message = _manual_source_payload(source_key, "")
        if manual_message and (source_df is None or source_df.empty):
            raise ValueError(manual_message)
        fields = _manual_filter_definitions(source_df, criteria, True)
        filtered_df, _active_filters = _apply_manual_filters(source_df, fields)
        if filtered_df.empty:
            raise ValueError(f'По сохранённому ручному фильтру «{filter_name}» нет данных для выгрузки.')
        export_frame = manual_filter_export_frame(filtered_df)
        buffer = BytesIO()
        write_single_sheet_excel(export_frame, buffer, sheet_name="Ручной фильтр")
        buffer.seek(0)
        return buffer.read()

    def _build_report_bytes_for_type(report_type: str) -> bytes:
        manual_filter_name = _parse_manual_mailing_report_name(report_type)
        if manual_filter_name:
            return _build_manual_saved_filter_report_bytes(manual_filter_name)
        if report_type == "approach":
            state = get_display_state(TAB_APPROACH, "")
            if state is None:
                raise ValueError("Нет данных для справки «Подход вагонов».")
            summary_source = filter_primary_destination(state.df)
            summary_df = build_summary_frame(summary_source)
            detail_source = filter_detail(state.df, report_dt=state.report_dt, primary_destination_only=True)
            detail_df = detail_export_frame(detail_source)
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "departure":
            state = get_display_state(TAB_DEPARTURE, "")
            if state is None:
                raise ValueError("Нет данных для справки «Отправление вагонов».")
            summary_df = build_summary_frame(state.df)
            detail_source = filter_detail(state.df, report_dt=state.report_dt)
            detail_df = detail_export_frame(detail_source)
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "idle_ugleuralskaya":
            state = get_display_state(TAB_STATION_IDLE, "", "ugleuralskaya")
            if state is None:
                raise ValueError("Нет данных для справки «Простой на станции Углеуральская».")
            summary_df = build_station_idle_frame(state.df, state.report_dt)
            detail_df = detail_export_frame(filter_detail(state.df, report_dt=state.report_dt, idle_mode="ugleuralskaya"))
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "idle_destination":
            state = get_display_state(TAB_STATION_IDLE, "", "destination")
            if state is None:
                raise ValueError("Нет данных для справки «Простой на станции назначения».")
            summary_df = build_station_destination_idle_frame(state.df, state.report_dt)
            detail_df = detail_export_frame(filter_detail(state.df, report_dt=state.report_dt, idle_mode="destination"))
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "raw_material":
            state = get_display_state(TAB_RAW_MATERIAL, "")
            if state is None:
                raise ValueError("Нет данных для справки «Сырье».")
            raw_df = filter_raw_material_idle(state.df, state.report_dt)
            summary_df = build_raw_material_idle_frame(state.df, state.report_dt)
            detail_df = detail_export_frame(filter_detail(raw_df, report_dt=state.report_dt))
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "loading_today":
            state = get_display_state(TAB_LOADING, "")
            if state is None:
                raise ValueError("Нет данных для справки «Погрузка сегодня».")
            loading_df = filter_loading_view(state.df, state.report_dt, "today")
            summary_df = build_summary_frame(loading_df)
            detail_df = detail_export_frame(filter_detail(loading_df, report_dt=state.report_dt))
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "loading_yesterday":
            state = get_display_state(TAB_LOADING, "")
            if state is None:
                raise ValueError("Нет данных для справки «Погрузка вчера».")
            loading_df = filter_loading_view(state.df, state.report_dt, "yesterday")
            summary_df = build_summary_frame(loading_df)
            detail_df = detail_export_frame(filter_detail(loading_df, report_dt=state.report_dt))
            return _build_workbook_bytes(summary_df, detail_df)
        if report_type == "loading_pending":
            state = get_display_state(TAB_LOADING, "")
            if state is None:
                raise ValueError("Нет данных для справки «Погружены, но не отправлены более суток».")
            loading_df = filter_loading_view(state.df, state.report_dt, "pending")
            summary_df = build_summary_frame(loading_df)
            detail_df = detail_export_frame(filter_detail(loading_df, report_dt=state.report_dt))
            return _build_workbook_bytes(summary_df, detail_df)
        raise ValueError(f"Неизвестный тип справки: {report_type}")

    def _state_report_day(state: Optional[SourceState]) -> Optional[date]:
        report_dt = getattr(state, "report_dt", None) if state is not None else None
        if isinstance(report_dt, datetime):
            return report_dt.date()
        if isinstance(report_dt, date):
            return report_dt
        return None

    def _format_calendar_date_label(value: Optional[date]) -> str:
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        return "—"

    def _format_filter_date_label(value: Optional[str]) -> str:
        parsed = parse_any_date(value)
        if parsed is not None:
            return parsed.strftime("%d.%m.%Y")
        return normalize_spaces(value) or "—"

    def _count_trip_end_for_day(state: SourceState, target_day: Optional[date], primary_destination_only: bool = False) -> int:
        if state is None or state.df is None or state.df.empty or target_day is None:
            return 0
        df = filter_detail(
            state.df,
            report_dt=state.report_dt,
            primary_destination_only=primary_destination_only,
            trip_end_date=target_day.isoformat(),
        )
        return int(len(df))

    def _count_departure_acceptance_for_day(state: SourceState, target_day: Optional[date]) -> int:
        if state is None or state.df is None or state.df.empty or target_day is None:
            return 0
        df = filter_detail(
            _with_departure_acceptance_display(state.df),
            report_dt=state.report_dt,
            departure_acceptance_date=target_day.isoformat(),
        )
        return int(len(df))

    def calculate_card_wagon_count(tab: str, station_name: str, state: SourceState) -> int:
        if tab == TAB_DEPARTURE:
            source_df = _apply_special_detail_source_filters(tab, state.df, station_name, None)
            df = filter_detail(source_df, destination=station_name)
            rows = build_train_presentation_rows(df, include_weight=True)
        else:
            special_approach_card = _normalize_special_approach_card_base(station_name) in _SPECIAL_APPROACH_CARD_BASES
            detail_kind = None if special_approach_card else ("ЦС" if _is_approach_direction(station_name) else None)
            source_df = _apply_special_detail_source_filters(tab, state.df, None, station_name)
            df = filter_detail(
                source_df,
                origin=None if special_approach_card else station_name,
                kind=detail_kind,
                primary_destination_only=False if special_approach_card else (tab == TAB_APPROACH),
            )
            rows = build_train_presentation_rows(df, include_weight=False)
        return count_train_card_wagons(rows)

    def _move_ugleuralskaya_row_first(rows: list[dict]) -> list[dict]:
        if not rows:
            return rows
        items = list(rows)
        target_index = None
        for index, row in enumerate(items):
            if str(row.get("level") or "") != "station":
                continue
            station_value = row.get("station") or row.get("label") or ""
            if is_ugleuralskaya_station(station_value):
                target_index = index
                break
        if target_index is None:
            return items
        target_row = items.pop(target_index)
        items.insert(0, target_row)
        return items

    def _clone_counts(counts: dict) -> dict:
        cloned: dict = {}
        if not isinstance(counts, dict):
            return cloned
        for category, cargo_counts in counts.items():
            if isinstance(cargo_counts, dict):
                cloned[category] = {cargo: int(cargo_counts.get(cargo, 0) or 0) for cargo in cargo_counts}
            else:
                cloned[category] = cargo_counts
        return cloned

    def _subtract_counts(base_counts: dict, minus_counts: dict) -> dict:
        result = _clone_counts(base_counts)
        if not isinstance(minus_counts, dict):
            return result
        for category, cargo_counts in minus_counts.items():
            if not isinstance(cargo_counts, dict):
                continue
            target = result.setdefault(category, {})
            if not isinstance(target, dict):
                target = {}
                result[category] = target
            for cargo, value in cargo_counts.items():
                current_value = int(target.get(cargo, 0) or 0)
                target[cargo] = max(0, current_value - int(value or 0))
        return result

    def _counts_total(counts: dict) -> int:
        if not isinstance(counts, dict):
            return 0
        total_bucket = counts.get("Всего", {})
        if isinstance(total_bucket, dict):
            return int(total_bucket.get("гр", 0) or 0) + int(total_bucket.get("пор", 0) or 0)
        return 0

    def _prepare_approach_summary_rows(rows: list[dict]) -> list[dict]:
        if not rows:
            return rows
        items = [dict(row) for row in rows]
        ug_row = None
        ug_road = None
        for row in items:
            if str(row.get("level") or "") != "station":
                continue
            station_value = row.get("station") or row.get("label") or ""
            if is_ugleuralskaya_station(station_value):
                ug_row = dict(row)
                ug_road = row.get("road")
                break
        if ug_row is None:
            return rows

        ug_counts = _clone_counts(ug_row.get("counts", {}))
        prepared: list[dict] = [ug_row]
        for row in items:
            level = str(row.get("level") or "")
            row_station = row.get("station") or row.get("label") or ""
            if level == "station" and is_ugleuralskaya_station(row_station):
                continue
            new_row = dict(row)
            if level == "total":
                new_row["counts"] = _subtract_counts(row.get("counts", {}), ug_counts)
            elif level == "road" and ug_road and row.get("road") == ug_road:
                new_row["counts"] = _subtract_counts(row.get("counts", {}), ug_counts)
                if _counts_total(new_row.get("counts", {})) == 0:
                    continue
            prepared.append(new_row)
        return prepared

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


    def _inject_ugleuralskaya_always_visible(html: str) -> str:
        if not html:
            return html
        selected_station = get_selected_station_name() or DEFAULT_WORK_STATION
        marker = "asu-selected-station-always-visible"
        if marker in html:
            return html
        station_json = json.dumps(selected_station, ensure_ascii=False)
        snippet = f"""
<style id="asu-selected-station-always-visible">
tr.asu-selected-station-always-visible{{display:table-row !important; visibility:visible !important;}}
tr.asu-selected-station-always-visible > th,
tr.asu-selected-station-always-visible > td,
tr.asu-selected-station-always-visible > th *,
tr.asu-selected-station-always-visible > td *{{color:#c00000 !important;}}
</style>
<script id="asu-selected-station-always-visible-script">
(function(){{
  var selectedStation = {station_json};
  function normalizeText(value){{
    return String(value || '').replace(/\s+/g, ' ').trim().toUpperCase().replace(/Ё/g, 'Е').replace(/\s*\(\d+\)\s*$/, '');
  }}
  function isSelectedStationRow(row){{
    if(!row || !selectedStation){{ return false; }}
    var cells = row.querySelectorAll('th, td');
    if(!cells.length){{ return false; }}
    var firstText = normalizeText(cells[0].textContent || '');
    var selectedText = normalizeText(selectedStation);
    return firstText === selectedText || firstText.indexOf(selectedText) !== -1 || selectedText.indexOf(firstText) !== -1;
  }}
  function getSelectedStationRows(){{
    return Array.from(document.querySelectorAll('tbody tr')).filter(isSelectedStationRow);
  }}
  function unhideSelectedStation(){{
    getSelectedStationRows().forEach(function(row){{
      row.classList.add('asu-selected-station-always-visible');
      row.classList.remove('is-collapsed');
      row.hidden = false;
      row.removeAttribute('hidden');
      row.style.setProperty('display', 'table-row', 'important');
      row.style.setProperty('visibility', 'visible', 'important');
      row.style.removeProperty('opacity');
      row.style.removeProperty('height');
      row.style.removeProperty('max-height');
      row.style.removeProperty('overflow');
    }});
  }}
  function scheduleUnhide(){{
    window.requestAnimationFrame(unhideSelectedStation);
    window.setTimeout(unhideSelectedStation, 0);
    window.setTimeout(unhideSelectedStation, 80);
  }}
  function bindControls(){{
    document.querySelectorAll('[data-road-toggle], #collapse-all-btn, #expand-all-btn').forEach(function(control){{
      if(control.dataset.selectedStationBound === '1'){{ return; }}
      control.dataset.selectedStationBound = '1';
      control.addEventListener('click', scheduleUnhide);
    }});
  }}
  function init(){{ bindControls(); scheduleUnhide(); }}
  if(document.readyState === 'loading'){{
    document.addEventListener('DOMContentLoaded', init);
  }} else {{
    init();
  }}
}})();
</script>
"""
        if "</body>" in html:
            return html.replace("</body>", snippet + "</body>", 1)
        return html + snippet

    def _ensure_mailing_report_registration(report_type: str, label: str) -> None:
        mailing_registry.register(
            report_type,
            label,
            lambda *, app, report_type, context, _rt=report_type: _build_report_bytes_for_type(_rt),
        )

    def _sync_mailing_report_registry() -> dict[str, str]:
        labels = _mailing_report_labels()
        for report_type, label in labels.items():
            _ensure_mailing_report_registration(report_type, label)
        return labels


    @app.route("/archive")
    def archive_search():
        wagon_input = str(request.args.get("wagon", "") or "").strip()
        wagon_numbers = parse_archive_wagon_numbers(wagon_input)
        station = normalize_spaces(request.args.get("station", ""))
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        station_options: list[str] = []
        archive_index = load_archive_index()
        try:
            station_names = set()
            for tab_items in archive_index.values() if isinstance(archive_index, dict) else []:
                if not isinstance(tab_items, list):
                    continue
                for item in tab_items:
                    if not isinstance(item, dict):
                        continue
                    file_path = Path(str(item.get("file_path") or ""))
                    if not file_path.exists():
                        continue
                    # Берём лишь подсказки по станциям из первых строк без тяжёлого полного обхода таблиц
                    try:
                        df = load_excel_as_df(str(file_path), mode=str(item.get("mode") or item.get("tab") or "approach"))
                    except Exception:
                        try:
                            mode = "departure" if "departure" in str(file_path).lower() else "approach"
                            df = load_excel_as_df(str(file_path), mode=mode)
                        except Exception:
                            continue
                    if "Станция операции" in df.columns:
                        for value in df["Станция операции"].dropna().head(200).tolist():
                            text_value = normalize_spaces(value)
                            if text_value:
                                station_names.add(text_value)
                    if len(station_names) >= 500:
                        break
            station_options = sorted(station_names, key=lambda value: value.upper().replace("Ё", "Е"))
        except Exception:
            station_options = []

        parsed_from = parse_iso_date(date_from)
        parsed_to = parse_iso_date(date_to)
        records = []
        requested_count = len(wagon_numbers)
        found_wagons: set[str] = set()
        not_found_wagons: list[str] = []
        search_performed = bool(wagon_input or date_from or date_to or station)
        empty_message = "Укажите один или несколько номеров вагонов и период поиска. Станцию можно не заполнять."

        if requested_count and parsed_from and parsed_to:
            index_exists, has_files = archive_files_status(archive_meta_path, parsed_from, parsed_to)
            if not index_exists:
                empty_message = "Архивный индекс не найден. Проверьте, формировался ли архив справок."
            elif not has_files:
                empty_message = "В архивном индексе нет доступных файлов за выбранный период. Проверьте папку архива и пути к файлам."
            else:
                records = search_archive_records(archive_meta_path, wagon_numbers, station, parsed_from, parsed_to)
                found_wagons = {
                    value for value in (normalize_wagon_number(item.get("wagon_number", "")) for item in records)
                    if value in set(wagon_numbers)
                }
                not_found_wagons = [value for value in wagon_numbers if value not in found_wagons]
                if records:
                    empty_message = ""
                else:
                    empty_message = (
                        "За выбранный период записи по указанным вагонам на этой станции не найдены."
                        if station else
                        "За выбранный период записи по указанным вагонам не найдены."
                    )
        elif search_performed:
            if not wagon_numbers:
                empty_message = "Введите один или несколько корректных номеров вагонов."
            elif not (parsed_from and parsed_to):
                empty_message = "Укажите дату начала и дату окончания периода поиска."

        filter_caption = "Архивные записи"
        if wagon_input or station or date_from or date_to:
            parts = []
            if wagon_numbers:
                parts.append(f"Вагонов в запросе: {len(wagon_numbers)}")
            if station:
                parts.append(f"Станция {station}")
            elif wagon_numbers:
                parts.append("Все станции")
            if date_from and date_to:
                parts.append(f"Период {date_from} — {date_to}")
            filter_caption = " / ".join(parts)

        archive_summary = ""
        if requested_count and parsed_from and parsed_to:
            archive_summary = f"Запрошено {requested_count} вагонов, найдено {len(found_wagons)} вагонов."

        export_link = ""
        if records:
            export_link = url_for(
                "archive_export",
                wagon=wagon_input,
                station=station,
                date_from=date_from,
                date_to=date_to,
            )

        archive_html = render_page(
            ARCHIVE_BODY,
            title=f"{APP_TITLE} — Архив",
            app_title=APP_TITLE,
            current_tab=TAB_ARCHIVE,
            current_tab_label=TAB_LABELS[TAB_ARCHIVE],
            wagon=wagon_input,
            station=station,
            date_from=date_from,
            date_to=date_to,
            station_options=station_options,
            records=records,
            total_count=len(records),
            requested_count=requested_count,
            found_wagon_count=len(found_wagons),
            not_found_wagons=not_found_wagons,
            archive_summary=archive_summary,
            filter_caption=filter_caption,
            empty_message=empty_message,
            error_message=pop_error(),
            success_message=pop_success(),
            export_link=export_link,
        )
        return _inject_detail_row_highlight(archive_html)

    @app.route("/archive/export")
    def archive_export():
        wagon_input = str(request.args.get("wagon", "") or "").strip()
        wagon_numbers = parse_archive_wagon_numbers(wagon_input)
        station = normalize_spaces(request.args.get("station", ""))
        date_from = request.args.get("date_from", "")
        date_to = request.args.get("date_to", "")
        parsed_from = parse_iso_date(date_from)
        parsed_to = parse_iso_date(date_to)
        if not wagon_numbers or parsed_from is None or parsed_to is None:
            set_error("Для выгрузки архива укажите один или несколько номеров вагонов и период.")
            return redirect(url_for("archive_search", wagon=wagon_input, station=station, date_from=date_from, date_to=date_to))

        records = search_archive_records(archive_meta_path, wagon_numbers, station, parsed_from, parsed_to)
        export_df = archive_export_frame(records)
        filename = f"Архив_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        buffer = BytesIO()
        write_single_sheet_excel(export_df, buffer, sheet_name="Архив")
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


    @app.errorhandler(404)
    def handle_404(_exc):
        return redirect(url_for("index", tab=get_tab_name(request.args.get("tab"))))

    @app.errorhandler(Exception)
    def handle_exception(exc):
        set_error(f"Ошибка: {exc}")
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        return render_page(
            INDEX_BODY,
            **common_index_context(
                tab,
                None,
                [],
                {
                    "metric_cards": [],
                    "category_order": CATEGORY_ORDER,
                    "cargo_order": CARGO_ORDER,
                    "summary_title": "Сводная таблица",
                    "summary_sub": "",
                    "summary_first_column": "Дорога / станция",
                    "show_expand_controls": False,
                },
            ),
        ), 500

    @app.before_request
    def enforce_license():
        if not app.config["LICENSE_SETTINGS"].get("enabled", True) or not app.config["LICENSE_SETTINGS"].get("require_license", True):
            return None
        endpoint = request.endpoint or ""
        allowed = {
            "license_center",
            "license_request_download",
            "license_upload",
            "license_remove",
            "license_status_json",
            "updates_check_json",
            "open_update_installer",
            "handle_404",
            "handle_exception",
            "static",
        }
        if endpoint in allowed:
            return None
        snapshot = get_license_snapshot()
        if snapshot["license_active"]:
            return None
        next_url = request.full_path if request.full_path else request.path
        if next_url.endswith("?"):
            next_url = next_url[:-1]
        return redirect(url_for("license_center", next=next_url))

    @app.route("/license")
    def license_center():
        snapshot = get_license_snapshot()
        update_info = get_update_snapshot()
        next_url = request.args.get("next", "")
        if not is_safe_next_url(next_url):
            next_url = url_for("index")
        return render_page(
            ACTIVATION_BODY,
            title=f"{APP_TITLE} — активация",
            activation_help_text=str(app.config["LICENSE_SETTINGS"].get("activation_help_text") or ""),
            next_url=next_url,
            update_info=update_info,
            error_message=pop_error(),
            success_message=pop_success(),
            **snapshot,
        )

    @app.route("/license/request")
    def license_request_download():
        payload = build_activation_request_payload(app.config["LICENSE_SETTINGS"])
        filename = build_activation_request_filename(payload, app.config["LICENSE_SETTINGS"])
        storage_dir = Path(get_license_snapshot()["storage_dir"])
        request_path = storage_dir / filename
        request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return send_file(request_path, as_attachment=True, download_name=filename, mimetype="application/json")

    @app.route("/license/upload", methods=["POST"])
    def license_upload():
        uploaded = request.files.get("license_file")
        next_url = request.form.get("next", "")
        if not is_safe_next_url(next_url):
            next_url = url_for("index")
        if not uploaded or not uploaded.filename:
            set_error("Файл лицензии не выбран.")
            return redirect(url_for("license_center", next=next_url))
        try:
            payload = install_license_file(uploaded.read(), base_dir, app.config["LICENSE_SETTINGS"])
            user_name = str(payload.get("user") or "пользователь")
            set_success(f"Лицензия успешно активирована: {user_name}")
            return redirect(next_url)
        except Exception as exc:
            set_error(f"Не удалось активировать лицензию: {exc}")
            return redirect(url_for("license_center", next=next_url))

    @app.route("/license/remove")
    def license_remove():
        try:
            remove_local_license(app.config["LICENSE_SETTINGS"])
            set_success("Локальная лицензия удалена.")
        except Exception as exc:
            set_error(f"Не удалось удалить лицензию: {exc}")
        return redirect(url_for("license_center"))

    @app.route("/license/status")
    def license_status_json():
        return jsonify(get_license_snapshot())

    @app.route("/updates/check")
    def updates_check_json():
        return jsonify(get_update_snapshot())

    @app.route("/updates/open")
    def open_update_installer():
        update_info = get_update_snapshot()
        installer_url = str(update_info.get("installer_url") or "").strip()
        if not installer_url:
            set_error("Ссылка на установщик обновления не задана.")
            return redirect(url_for("license_center"))
        return redirect(installer_url)

    @app.route("/manual-filters/save", methods=["POST"])
    def manual_filters_save():
        name = _normalize_manual_text(request.form.get("manual_filter_name"))
        if not name:
            set_error("Не указано название списка для сохранения.")
            return redirect(_manual_redirect_url(request.form))
        source_key = _normalize_manual_text(request.form.get("manual_source")) or "approach"
        criteria: dict[str, object] = {}
        for key in ["kind", "cargo_state", "trip_start_from", "trip_start_to", "operation_date_from", "operation_date_to", "owner", "cargo_name", "shipper", "consignee", "origin_road", "destination_road", "origin_station", "destination", "station", "wagon_number"]:
            values = [item for item in request.form.getlist(key) if _normalize_manual_text(item)]
            if key == "kind":
                criteria[key] = values
            else:
                criteria[key] = _normalize_manual_text(request.form.get(key))
        items = [item for item in _manual_saved_filters() if str(item.get("name") or "") != name]
        items.append({
            "name": name,
            "source_key": source_key,
            "criteria": criteria,
            "saved_at": now().isoformat(),
        })
        _save_manual_saved_filters(items)
        _sync_mailing_report_registry()
        set_success(f"Фильтр «{name}» сохранён.")
        target = _manual_redirect_url(request.form)
        joiner = "&" if "?" in target else "?"
        return redirect(target + joiner + urlencode({"saved_filter": name}))

    @app.route("/manual-filters/delete", methods=["POST"])
    def manual_filters_delete():
        name = _normalize_manual_text(request.form.get("saved_filter"))
        if not name:
            set_error("Не выбран сохранённый фильтр для удаления.")
            return redirect(_manual_redirect_url(request.form))
        items = [item for item in _manual_saved_filters() if str(item.get("name") or "") != name]
        _save_manual_saved_filters(items)
        _sync_mailing_report_registry()
        set_success(f"Фильтр «{name}» удалён.")
        return redirect(_manual_redirect_url(request.form))


    @app.route("/manual-filter/export", methods=["GET", "POST"])
    def manual_filter_export():
        archive_date = request.values.get("archive_date", "")
        source_labels = _manual_source_labels()
        selected_saved_filter = _normalize_manual_text(request.values.get("saved_filter"))
        selected_source = _normalize_manual_text(request.values.get("manual_source")) or "approach"
        filtered_rows_df = _parse_filtered_rows_payload(request.form.get("filtered_rows"), [
            "№ вагона",
            "Род вагона",
            "Состояние",
            "Собственник",
            "Груз",
            "Грузоотправитель",
            "Грузополучатель",
            "Станция отправления",
            "Дорога отправления",
            "Станция назначения",
            "Дорога назначения",
            "Станция операции",
            "Дорога операции",
            "Операция",
            "Дата операции",
        ]) if request.method == "POST" else None
        state, source_df, source_label, manual_message = _manual_source_payload(selected_source, archive_date)
        if manual_message and (source_df is None or source_df.empty):
            set_error(manual_message)
            return redirect(url_for("index") + "?" + urlencode(request.args.items(multi=True), doseq=True))
        if filtered_rows_df is not None:
            if filtered_rows_df.empty:
                set_error("По текущему ручному фильтру нечего выгружать в Excel.")
                return redirect(url_for("index", tab=TAB_MANUAL, manual_source=selected_source, archive_date=archive_date))
            export_frame = filtered_rows_df
        else:
            fields = _manual_filter_definitions(source_df)
            filtered_df, _ = _apply_manual_filters(source_df, fields)
            if filtered_df.empty:
                set_error("По текущему ручному фильтру нечего выгружать в Excel.")
                return redirect(url_for("index") + "?" + urlencode(
                    _manual_query_pairs_from_fields(selected_source, archive_date, selected_saved_filter, fields, drop_saved_filter=True),
                    doseq=True,
                ))
            export_frame = manual_filter_export_frame(filtered_df)
        buffer = BytesIO()
        write_single_sheet_excel(export_frame, buffer, sheet_name="Ручной фильтр")
        buffer.seek(0)
        filename = _manual_export_filename(selected_source, selected_saved_filter)
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )


    @app.route("/station-select", methods=["GET", "POST"])
    def station_select():
        if request.method == "POST":
            try:
                station = save_selected_station(request.form.get("station"))
                set_success(f"Выбрана станция: {station}")
            except Exception as exc:
                set_error(str(exc) or "Не удалось выбрать станцию.")
        return redirect(url_for("index", tab=TAB_DASHBOARD))

    @app.route("/station-select/clear")
    def station_clear():
        clear_selected_station_file()
        set_success("Выбор станции сброшен.")
        return redirect(url_for("index", tab=TAB_DASHBOARD))

    @app.route("/")
    def index():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        if tab == TAB_DASHBOARD:
            return render_page(DASHBOARD_BODY, **_build_dashboard_context())
        if tab == TAB_STATION_SELECT:
            return redirect(url_for("index", tab=TAB_DASHBOARD))
        if tab == TAB_SETTINGS:
            return redirect(url_for("settings_page"))
        if tab == TAB_MANUAL:
            return render_page(MANUAL_FILTER_BODY, **build_manual_filter_context())
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view")) if tab == TAB_LOADING else "today"
        cargo_name_filter = normalize_spaces(request.args.get("cargo_name_filter")) or None
        approach_cargo_filter = normalize_spaces(request.args.get("approach_cargo_filter")) or None
        approach_previous_cargo_filter = normalize_spaces(request.args.get("approach_previous_cargo_filter")) or None
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            extra = {
                "metric_cards": [],
                "category_order": CATEGORY_ORDER,
                "cargo_order": CARGO_ORDER,
                "summary_title": "Сводная таблица",
                "summary_sub": "",
                "summary_first_column": "Дорога / станция",
                "show_expand_controls": False,
                "raw_material_table": False,
                "raw_material_headers": [],
                "raw_material_rows": [],
            }
            return render_page(INDEX_BODY, **common_index_context(tab, None, [], extra))

        if tab == TAB_LOADING and loading_view == "month":
            return build_loading_month_page(state, request.args.get("loading_month"), request.args.get("selected_cargo"))

        rows = []
        metric_cards: list[dict] = []
        summary_title = "Сводная таблица"
        summary_sub = ""
        summary_first_column = "Дорога / станция"
        show_expand_controls = tab in {TAB_APPROACH, TAB_DEPARTURE}
        category_order = CATEGORY_ORDER
        cargo_order = CARGO_ORDER
        raw_material_table = False
        raw_material_headers: list[str] = []
        raw_material_rows: list[dict] = []
        summary_cargo_filter_label = ""
        summary_cargo_filter_options: list[str] = []
        summary_cargo_filter_value = cargo_name_filter or ""
        approach_cargo_filter_options: list[str] = []
        approach_previous_cargo_filter_options: list[str] = []
        if tab == TAB_APPROACH:
            approach_cargo_filter_options = _unique_filter_options(state.df, ["cargo_name_display", "Наименование груза", "Груз"])
            approach_previous_cargo_filter_options = _unique_filter_options(state.df, ["previous_cargo_display", "Ранее выгруженный груз"])
            if approach_cargo_filter or approach_previous_cargo_filter:
                state = _state_with_df(
                    state,
                    _apply_approach_header_filters(state.df, approach_cargo_filter, approach_previous_cargo_filter),
                )

        if tab == TAB_STATION_IDLE:
            if idle_view == "destination":
                idle_rows = build_station_destination_idle_rows(state.df, state.report_dt, cargo_name_filter=cargo_name_filter)
                summary_title = ""
                summary_sub = ""
                summary_first_column = "Станция назначения / интервал"
                show_expand_controls = True
            else:
                idle_rows = build_station_idle_rows(state.df, state.report_dt)
                summary_title = f"Простой на станции {get_selected_station_name() or DEFAULT_WORK_STATION}"
                summary_sub = ""
                summary_first_column = "Интервал"
                show_expand_controls = False

            for row in idle_rows:
                row_destination = row.get("destination_station") if idle_view == "destination" else None
                idle_category_order = STATION_IDLE_CATEGORY_ORDER if idle_view == "destination" else STATION_IDLE_UGL_CATEGORY_ORDER
                row_cargo_name_filter = None
                if idle_view == "destination":
                    row_cargo_name_filter = row.get("cargo_name") or cargo_name_filter
                row_links = {
                    col: {
                        cargo: build_link(
                            tab=tab,
                            kind=None if col == "Всего" else col,
                            cargo=cargo,
                            station=row_destination if idle_view == "destination" else None,
                            destination=None if idle_view == "destination" else row_destination,
                            idle_bucket=row.get("idle_bucket"),
                            idle_view=idle_view,
                            archive_date=archive_date,
                            cargo_name_filter=row_cargo_name_filter,
                        )
                        for cargo in CARGO_ORDER
                    }
                    for col in idle_category_order
                }
                row_map_link = None
                if idle_view == "destination" and row.get("level") == "road" and row.get("destination_station"):
                    row_map_link = build_map_link(
                        tab=tab,
                        archive_date=archive_date,
                        idle_view=idle_view,
                        station=row.get("destination_station"),
                        cargo_name_filter=cargo_name_filter,
                    )
                rows.append({**row, "links": row_links, "map_link": row_map_link})

            category_order = STATION_IDLE_CATEGORY_ORDER if idle_view == "destination" else STATION_IDLE_UGL_CATEGORY_ORDER
            if idle_view == "destination":
                idle_source_df = filter_station_destination_idle(state.df)
                if not idle_source_df.empty:
                    cargo_series = idle_source_df.get("Наименование груза", pd.Series("", index=idle_source_df.index)).fillna("").astype(str).map(normalize_spaces)
                    cargo_series = cargo_series.where(cargo_series != "", "Без указания")
                    summary_cargo_filter_label = "Наименование груза"
                    summary_cargo_filter_options = sorted(
                        cargo_name
                        for cargo_name in cargo_series.dropna().unique().tolist()
                        if normalize_spaces(cargo_name)
                    )
            total_idle = idle_rows[0]["counts"]["Всего"]["гр"] + idle_rows[0]["counts"]["Всего"]["пор"] if idle_rows else 0
            metric_cards = [
                {
                    "label": "Всего",
                    "count": total_idle,
                    "sub": "Суммарно по выбранной справке",
                    "link": build_link(tab=tab, idle_view=idle_view, archive_date=archive_date, cargo_name_filter=cargo_name_filter) if total_idle else None,
                    "danger": False,
                },
                {
                    "label": "30 суток и более",
                    "count": sum(
                        row["counts"]["Всего"]["гр"] + row["counts"]["Всего"]["пор"]
                        for row in idle_rows
                        if row.get("idle_bucket") == "30plus"
                    ),
                    "sub": "",
                    "link": build_link(tab=tab, idle_bucket="30plus", idle_view=idle_view, archive_date=archive_date, cargo_name_filter=cargo_name_filter),
                    "danger": True,
                },
            ]
        elif tab == TAB_RAW_MATERIAL:
            cargo_headers, matrix_rows, raw_total_count, raw_max_days = build_raw_material_idle_rows(state.df, state.report_dt)
            raw_material_table = True
            raw_material_headers = cargo_headers
            raw_material_rows = []
            for row in matrix_rows:
                row_links = {
                    cargo_name: build_link(
                        tab=tab,
                        archive_date=archive_date,
                        raw_material_cargo=cargo_name,
                        raw_material_days=row.get("idle_days"),
                    )
                    for cargo_name in cargo_headers
                }
                raw_material_rows.append({**row, "links": row_links})
            summary_title = 'простой сырья на путях АО "МЕТАФРАКС КЕМИКАЛС"'
            summary_sub = ""
            summary_first_column = "ИНТЕРВАЛ"
            show_expand_controls = False
            metric_cards = [
                {
                    "label": "Всего вагонов",
                    "count": raw_total_count,
                    "sub": "",
                    "link": build_link(tab=tab, archive_date=archive_date) if raw_total_count > 0 else None,
                    "danger": False,
                },
                {
                    "label": "Наименований грузов",
                    "count": len(cargo_headers),
                    "sub": "",
                    "link": None,
                    "danger": False,
                },
                {
                    "label": "Макс. простой",
                    "count": (f"свыше {RAW_MATERIAL_IDLE_LIMIT_DAYS}" if raw_max_days > RAW_MATERIAL_IDLE_LIMIT_DAYS else raw_max_days),
                    "sub": "",
                    "link": None,
                    "danger": False,
                },
            ]
        elif tab == TAB_LOADING:
            loading_view = get_loading_view(request.args.get("loading_view"))
            loading_df = filter_loading_view(state.df, state.report_dt, loading_view)
            for row in build_summary_rows(loading_df):
                row_links = {
                    col: {
                        cargo: build_link(
                            tab=tab,
                            road=row.get("road"),
                            station=row.get("station"),
                            kind=None if col == "Всего" else col,
                            cargo=cargo,
                            loading_view=loading_view,
                            archive_date=archive_date,
                        )
                        for cargo in CARGO_ORDER
                    }
                    for col in CATEGORY_ORDER
                }
                rows.append({**row, "links": row_links, "map_link": None})

            today_count = int(len(filter_loading_view(state.df, state.report_dt, "today")))
            yesterday_count = int(len(filter_loading_view(state.df, state.report_dt, "yesterday")))
            pending_count = int(len(filter_loading_view(state.df, state.report_dt, "pending")))
            if loading_view == "today":
                metric_cards = [
                    {
                        "label": "Погрузка сегодня",
                        "count": today_count,
                        "sub": "",
                        "link": build_link(tab=tab, loading_view="today", archive_date=archive_date) if today_count > 0 else None,
                        "danger": False,
                    }
                ]
                summary_title = "Погрузка сегодня"
            elif loading_view == "yesterday":
                metric_cards = [
                    {
                        "label": "Погрузка вчера",
                        "count": yesterday_count,
                        "sub": f"Дата начала рейса: {(moscow_today() - timedelta(days=1)).strftime('%d.%m.%Y')}",
                        "link": build_link(tab=tab, loading_view="yesterday", archive_date=archive_date) if yesterday_count > 0 else None,
                        "danger": False,
                    }
                ]
                summary_title = "Погрузка вчера"
            else:
                metric_cards = [
                    {
                        "label": "Погружены, но не отправлены более суток",
                        "count": pending_count,
                        "sub": "",
                        "link": build_link(tab=tab, loading_view="pending", archive_date=archive_date) if pending_count > 0 else None,
                        "danger": False,
                    }
                ]
                summary_title = "Погружены, но не отправлены более суток"
            summary_sub = ""
            summary_first_column = "Дорога / станция"
            show_expand_controls = True
        else:
            summary_df = filter_primary_destination(state.df) if tab == TAB_APPROACH else _positive_distance_df(state.df)
            raw_summary_rows = build_summary_rows(summary_df)
            summary_rows_for_display = _prepare_approach_summary_rows(raw_summary_rows) if tab == TAB_APPROACH else raw_summary_rows
            ugleuralskaya_road = None
            if tab == TAB_APPROACH:
                for _summary_row in raw_summary_rows:
                    if str(_summary_row.get("level") or "") != "station":
                        continue
                    station_value = _summary_row.get("station") or _summary_row.get("label") or ""
                    if is_ugleuralskaya_station(station_value):
                        ugleuralskaya_road = _summary_row.get("road")
                        break
            for row in summary_rows_for_display:
                exclude_ugleuralskaya_for_row = bool(
                    tab == TAB_APPROACH and (
                        str(row.get("level") or "") == "total"
                        or (
                            str(row.get("level") or "") == "road"
                            and ugleuralskaya_road
                            and row.get("road") == ugleuralskaya_road
                        )
                    )
                )
                row_links = {
                    col: {
                        cargo: build_link(
                            tab=tab,
                            road=row.get("road"),
                            station=row.get("station"),
                            kind=None if col == "Всего" else col,
                            cargo=cargo,
                            primary_only=(tab == TAB_APPROACH),
                            archive_date=archive_date,
                            exclude_ugleuralskaya=exclude_ugleuralskaya_for_row,
                        )
                        for cargo in CARGO_ORDER
                    }
                    for col in CATEGORY_ORDER
                }
                row_map_link = None
                if row.get("level") == "station" and row.get("station"):
                    row_map_link = build_map_link(
                        tab=tab,
                        archive_date=archive_date,
                        road=row.get("road"),
                        station=row.get("station"),
                        primary_only=(tab == TAB_APPROACH),
                    )
                rows.append({**row, "links": row_links, "map_link": row_map_link})

            stop_count = len(get_visible_stop_rent_records(tab, state.report_dt))
            if tab == TAB_APPROACH:
                overdue_count = int(
                    len(
                        filter_detail(
                            state.df,
                            overdue_delivery=True,
                            report_dt=state.report_dt,
                            primary_destination_only=True,
                        )
                    )
                )
                formed_count = count_formed_trains(summary_df)
                metric_cards = [
                    {
                        "label": "Нарушен срок доставки",
                        "count": overdue_count,
                        "sub": "",
                        "link": build_link(tab=tab, overdue_delivery=True, primary_only=True, archive_date=archive_date) if overdue_count > 0 else None,
                        "danger": True,
                    },
                    {
                        "label": "Стоп аренда",
                        "count": stop_count,
                        "sub": "Активные и за 3 суток после завершения",
                        "link": url_for("stop_rent_access", tab=tab, archive_date=archive_date),
                        "danger": False,
                    },
                    {
                        "label": "Сформированные поезда",
                        "count": formed_count,
                        "sub": f"Назначением на {get_selected_station_name() or DEFAULT_WORK_STATION}",
                        "link": build_link(tab=tab, formed_trains=True, primary_only=True, archive_date=archive_date) if formed_count > 0 else None,
                        "danger": False,
                    },
                ]
                today_date = moscow_today()
                yesterday_date = today_date - timedelta(days=1)
                arrived_today_count = _count_trip_end_for_day(state, today_date, primary_destination_only=True)
                arrived_yesterday_count = _count_trip_end_for_day(state, yesterday_date, primary_destination_only=True)
                metric_cards.extend([
                    {
                        "label": "Прибыло сегодня",
                        "count": arrived_today_count,
                        "sub": f"Дата окончания рейса: {_format_calendar_date_label(today_date)}",
                        "link": build_link(tab=tab, archive_date=archive_date, primary_only=True, trip_end_date=today_date.isoformat()) if arrived_today_count > 0 and today_date is not None else None,
                        "danger": False,
                    },
                    {
                        "label": "Прибыло вчера",
                        "count": arrived_yesterday_count,
                        "sub": f"Дата окончания рейса: {_format_calendar_date_label(yesterday_date)}",
                        "link": build_link(tab=tab, archive_date=archive_date, primary_only=True, trip_end_date=yesterday_date.isoformat()) if arrived_yesterday_count > 0 and yesterday_date is not None else None,
                        "danger": False,
                    },
                ])
                for station_name in get_approach_direction_cards():
                    count_value = calculate_card_wagon_count(tab, station_name, state)
                    metric_cards.append(
                        {
                            "label": station_name,
                            "count": count_value,
                            "sub": "Станция отправления",
                            "link": build_link(
                                tab=tab,
                                origin=station_name,
                                kind=None if _normalize_special_approach_card_base(station_name) in _SPECIAL_APPROACH_CARD_BASES else "ЦС",
                                archive_date=archive_date,
                            ) if count_value > 0 else None,
                            "danger": False,
                        }
                    )
                summary_sub = f"Назначение: {get_selected_station_name() or DEFAULT_WORK_STATION}"
            else:
                metric_cards = [
                    {
                        "label": "Всего",
                        "count": int(len(summary_df)),
                        "sub": f"Все вагоны со станции {get_selected_station_name() or DEFAULT_WORK_STATION}",
                        "link": build_link(tab=tab, archive_date=archive_date),
                    },
                    {
                        "label": "Гружёных",
                        "count": int(len(filter_detail(summary_df, cargo="гр"))),
                        "sub": "",
                        "link": build_link(tab=tab, cargo="гр", archive_date=archive_date),
                    },
                    {
                        "label": "Стоп аренда",
                        "count": stop_count,
                        "sub": "Активные и за 3 суток после завершения",
                        "link": url_for("stop_rent_access", tab=tab, archive_date=archive_date),
                        "danger": False,
                    },
                ]
                today_date = moscow_today()
                yesterday_date = today_date - timedelta(days=1)
                sent_today_count = _count_departure_acceptance_for_day(state, today_date)
                sent_yesterday_count = _count_departure_acceptance_for_day(state, yesterday_date)
                metric_cards.extend([
                    {
                        "label": "Отправлено сегодня",
                        "count": sent_today_count,
                        "sub": f"Отпр. со ст. приёма: {_format_calendar_date_label(today_date)}",
                        "link": build_link(tab=tab, archive_date=archive_date, departure_acceptance_date=today_date.isoformat()) if sent_today_count > 0 and today_date is not None else None,
                    },
                    {
                        "label": "Отправлено вчера",
                        "count": sent_yesterday_count,
                        "sub": f"Отпр. со ст. приёма: {_format_calendar_date_label(yesterday_date)}",
                        "link": build_link(tab=tab, archive_date=archive_date, departure_acceptance_date=yesterday_date.isoformat()) if sent_yesterday_count > 0 and yesterday_date is not None else None,
                    },
                ])
                for station_name in get_departure_direction_cards():
                    count_value = calculate_card_wagon_count(tab, station_name, state)
                    metric_cards.append(
                        {
                            "label": station_name,
                            "count": count_value,
                            "sub": "Станция назначения",
                            "link": build_link(tab=tab, destination=station_name, archive_date=archive_date) if count_value > 0 else None,
                        }
                    )
                summary_sub = f"Отправление со станции: {get_selected_station_name() or DEFAULT_WORK_STATION}"

        extra = {
            "metric_cards": metric_cards,
            "category_order": category_order,
            "cargo_order": cargo_order,
            "summary_title": summary_title,
            "summary_sub": summary_sub,
            "summary_first_column": summary_first_column,
            "show_expand_controls": show_expand_controls,
            "raw_material_table": raw_material_table,
            "raw_material_headers": raw_material_headers,
            "raw_material_rows": raw_material_rows,
            "summary_cargo_filter_label": summary_cargo_filter_label,
            "summary_cargo_filter_options": summary_cargo_filter_options,
            "summary_cargo_filter_value": summary_cargo_filter_value,
            "approach_cargo_filter_options": approach_cargo_filter_options,
            "approach_previous_cargo_filter_options": approach_previous_cargo_filter_options,
            "approach_cargo_filter_value": approach_cargo_filter or "",
            "approach_previous_cargo_filter_value": approach_previous_cargo_filter or "",
        }
        page_html = render_page(INDEX_BODY, **common_index_context(tab, state, rows, extra))
        if tab == TAB_APPROACH:
            page_html = _inject_ugleuralskaya_always_visible(page_html)
        return page_html

    @app.route("/settings", methods=["GET", "POST"])
    def settings_page():
        if request.method == "POST":
            action = normalize_spaces(request.form.get("action")).lower()
            if action == "save_station_source":
                station_name = normalize_station_name(request.form.get("station_name"))
                if not station_name:
                    set_error("Укажите наименование станции.")
                    return redirect(url_for("settings_page") + "#stations")
                if is_base_station(station_name):
                    set_error("Станция Углеуральская является базовой и не настраивается через этот блок.")
                    return redirect(url_for("settings_page") + "#stations")
                items = load_station_sources()
                key = normalize_station_key(station_name)
                existing = None
                for item in items:
                    if normalize_station_key(item.get("name")) == key:
                        existing = item
                        break
                if existing is None:
                    existing = _blank_station_source_config(station_name)
                    items.append(existing)
                existing["name"] = station_name
                existing["station_key"] = key
                existing["slug"] = _station_slug(station_name)
                existing["enabled"] = str(request.form.get("station_enabled") or "1") == "1"
                existing["approach"] = {
                    "mailbox": normalize_spaces(request.form.get("approach_mailbox")),
                    "subject_filter": normalize_spaces(request.form.get("approach_subject_filter")),
                    "subject_equals": normalize_spaces(request.form.get("approach_subject_equals")),
                    "attachment_name_contains": normalize_spaces(request.form.get("approach_attachment_name_contains")),
                    "attachment_name_equals": normalize_spaces(request.form.get("approach_attachment_name_equals")),
                }
                existing["departure"] = {
                    "mailbox": normalize_spaces(request.form.get("departure_mailbox")),
                    "subject_filter": normalize_spaces(request.form.get("departure_subject_filter")),
                    "subject_equals": normalize_spaces(request.form.get("departure_subject_equals")),
                    "attachment_name_contains": normalize_spaces(request.form.get("departure_attachment_name_contains")),
                    "attachment_name_equals": normalize_spaces(request.form.get("departure_attachment_name_equals")),
                }
                existing["directions"] = {
                    "approach": _build_direction_config_from_form("approach"),
                    "departure": _build_direction_config_from_form("departure"),
                }
                save_station_sources(items)
                set_success(f"Настройки станции «{station_name}» сохранены.")
                return redirect(url_for("settings_page") + "#stations")
            if action == "save_station_directions":
                station_name = normalize_station_name(request.form.get("station_name"))
                key = normalize_station_key(station_name)
                if not key or is_base_station(station_name):
                    set_error("Для базовой станции быстрые направления через этот блок не меняются.")
                    return redirect(url_for("settings_page") + "#stations")
                items = load_station_sources()
                updated = False
                for item in items:
                    if normalize_station_key(item.get("name")) == key:
                        item["directions"] = {
                            "approach": _build_direction_config_from_form("approach"),
                            "departure": _build_direction_config_from_form("departure"),
                        }
                        updated = True
                        break
                if not updated:
                    set_error("Добавленная станция не найдена.")
                    return redirect(url_for("settings_page") + "#stations")
                save_station_sources(items)
                set_success(f"Быстрые направления станции «{station_name}» сохранены.")
                return redirect(url_for("settings_page") + "#stations")
            if action == "delete_station_source":
                station_name = normalize_station_name(request.form.get("station_name"))
                key = normalize_station_key(station_name)
                if not key or is_base_station(station_name):
                    set_error("Базовую станцию удалить нельзя.")
                    return redirect(url_for("settings_page") + "#stations")
                items = [item for item in load_station_sources() if normalize_station_key(item.get("name")) != key]
                save_station_sources(items)
                if normalize_station_key(get_selected_station_name()) == key:
                    clear_selected_station_file()
                    set_state(TAB_APPROACH, None)
                    set_state(TAB_DEPARTURE, None)
                set_success(f"Станция «{station_name}» удалена из добавленных станций.")
                return redirect(url_for("settings_page") + "#stations")
            if action == "save_channel":
                save_notification_channel({
                    "channel_type": normalize_spaces(request.form.get("channel_type")) or "app",
                    "channel_target": str(request.form.get("channel_target") or "").strip(),
                    "channel_url": str(request.form.get("channel_url") or "").strip(),
                    "channel_comment": str(request.form.get("channel_comment") or "").strip(),
                    "phone": str(request.form.get("phone") or "").strip(),
                    "telegram_target": str(request.form.get("telegram_target") or "").strip(),
                    "whatsapp_target": str(request.form.get("whatsapp_target") or "").strip(),
                    "max_target": str(request.form.get("max_target") or "").strip(),
                })
                set_success("Каналы связи сохранены.")
                return redirect(url_for("settings_page"))
            if action == "save_appearance":
                prefs = load_ui_preferences()
                prefs.update({
                    "theme": normalize_spaces(request.form.get("theme")).lower() or "light",
                    "radius_style": normalize_spaces(request.form.get("radius_style")).lower() or "soft",
                    "density": normalize_spaces(request.form.get("density")).lower() or "standard",
                    "accent_color": str(request.form.get("accent_color") or "#2456d4").strip() or "#2456d4",
                    "font_color": str(request.form.get("font_color") or "#182433").strip() or "#182433",
                })
                save_ui_preferences(prefs)
                app.config["UI_PREFERENCES"] = load_ui_preferences()
                set_success("Внешний вид сохранён.")
                return redirect(url_for("settings_page"))
            if action == "save_dashboard":
                prefs = load_ui_preferences()
                prefs.update({
                    "default_map_view": normalize_spaces(request.form.get("default_map_view")).lower() or "loaded",
                    "dashboard_events_limit": max(3, min(20, int(request.form.get("dashboard_events_limit") or 8))),
                    "dashboard_show_map": str(request.form.get("dashboard_show_map") or "") == "1",
                })
                save_ui_preferences(prefs)
                app.config["UI_PREFERENCES"] = load_ui_preferences()
                set_success("Настройки стартового экрана сохранены.")
                return redirect(url_for("settings_page"))
            if action == "save_export":
                export_prefs = {
                    "excel_as_table": str(request.form.get("excel_as_table") or "") == "1",
                    "excel_with_filters": str(request.form.get("excel_with_filters") or "") == "1",
                    "excel_with_borders": str(request.form.get("excel_with_borders") or "") == "1",
                    "excel_freeze_header": str(request.form.get("excel_freeze_header") or "") == "1",
                    "excel_header_color": str(request.form.get("excel_header_color") or "#dfeaff").strip() or "#dfeaff",
                    "excel_header_font_color": str(request.form.get("excel_header_font_color") or "#1f3352").strip() or "#1f3352",
                }
                save_export_preferences(export_prefs)
                app.config["EXPORT_PREFERENCES"] = load_export_preferences()
                set_success("Настройки Excel сохранены.")
                return redirect(url_for("settings_page"))
            if action == "save_program":
                prefs = load_ui_preferences()
                prefs.update({
                    "startup_tab": normalize_spaces(request.form.get("startup_tab")).lower() or "dashboard",
                    "dashboard_refresh_seconds": max(0, min(3600, int(request.form.get("dashboard_refresh_seconds") or 0))),
                })
                save_ui_preferences(prefs)
                app.config["UI_PREFERENCES"] = load_ui_preferences()
                set_success("Поведение программы сохранено.")
                return redirect(url_for("settings_page"))
            if action == "add_rule":
                name = normalize_spaces(request.form.get("rule_name"))
                if not name:
                    set_error("Укажите название правила.")
                    return redirect(url_for("settings_page"))
                rules = load_notification_rules()
                rules.append({
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "event_type": normalize_spaces(request.form.get("event_type")) or "operation_changed",
                    "entity_type": normalize_spaces(request.form.get("entity_type")) or "wagon",
                    "station_name": normalize_spaces(request.form.get("station_name")),
                    "cargo_state": normalize_spaces(request.form.get("cargo_state")) or "all",
                    "delivery_channel": normalize_spaces(request.form.get("delivery_channel")) or "app",
                    "train_index": normalize_spaces(request.form.get("train_index")),
                    "wagon_number": normalize_spaces(request.form.get("wagon_number")),
                    "note": normalize_spaces(request.form.get("rule_note")),
                })
                save_notification_rules(rules)
                set_success("Правило уведомления добавлено.")
                return redirect(url_for("settings_page"))
            if action == "delete_rule":
                rule_id = normalize_spaces(request.form.get("rule_id"))
                rules = [item for item in load_notification_rules() if str(item.get("id") or "") != rule_id]
                save_notification_rules(rules)
                set_success("Правило удалено.")
                return redirect(url_for("settings_page"))
        return render_page(SETTINGS_BODY, **_build_settings_context())

    @app.route("/search-wagon")
    def search_wagon():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            set_error("Сначала загрузите Excel для выбранной вкладки.")
            return redirect(url_for("index", tab=tab, idle_view=idle_view))
        wagon = request.args.get("wagon", "").strip()
        if not wagon:
            set_error("Введите точный номер вагона.")
            return redirect(url_for("index", tab=tab, archive_date=archive_date, idle_view=idle_view))
        normalized = normalize_wagon_number(wagon)
        idle_mode = idle_view if tab == TAB_STATION_IDLE else None
        loading_view = get_loading_view(request.args.get("loading_view"))
        source_df = state.df
        if tab == TAB_LOADING:
            source_df = filter_loading_view(source_df, state.report_dt, loading_view)
        elif tab == TAB_RAW_MATERIAL:
            source_df = filter_raw_material_idle(source_df, state.report_dt)
        match_df = filter_detail(source_df, exact_wagon=normalized, report_dt=state.report_dt, primary_destination_only=False, idle_mode=idle_mode)
        if match_df.empty:
            set_error(f"Вагон {normalized} не найден.")
            return redirect(url_for("index", tab=tab, wagon=normalized, archive_date=archive_date, idle_view=idle_view, loading_view=loading_view if tab == TAB_LOADING else None))
        return redirect(url_for("details", tab=tab, wagon=normalized, archive_date=archive_date, idle_view=idle_view, loading_view=loading_view if tab == TAB_LOADING else None))

    @app.route("/upload", methods=["POST"])
    def upload_file():
        display_tab = get_tab_name(request.form.get("tab"))
        idle_view = get_idle_view(request.form.get("idle_view"))
        loading_view = get_loading_view(request.form.get("loading_view")) if display_tab == TAB_LOADING else "today"
        loading_month = normalize_month_key(request.form.get("loading_month")) if display_tab == TAB_LOADING and loading_view == "month" else None
        selected_cargo = normalize_spaces(request.form.get("selected_cargo")) if display_tab == TAB_LOADING and loading_view == "month" else None
        tab = get_station_idle_source_tab(idle_view) if display_tab == TAB_STATION_IDLE else get_source_tab(display_tab)
        uploaded = request.files.get("excel_file")
        if not uploaded or not uploaded.filename:
            set_error("Файл не выбран.")
            return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        safe_name = secure_filename(uploaded.filename) or f"report_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        target_path = upload_dir / f"{tab}_{safe_name}"
        try:
            uploaded.save(target_path)
            load_from_path(str(target_path), mode=tab, source_name=uploaded.filename)
            set_success(f"Файл загружен во вкладку «{TAB_LABELS[tab]}»: {uploaded.filename}")
        except Exception as exc:
            set_error(f"Не удалось обработать Excel: {exc}")
        return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))

    @app.route("/refresh")
    def refresh():
        display_tab = get_tab_name(request.args.get("tab"))
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view")) if display_tab == TAB_LOADING else "today"
        loading_month = normalize_month_key(request.args.get("loading_month")) if display_tab == TAB_LOADING and loading_view == "month" else None
        selected_cargo = normalize_spaces(request.args.get("selected_cargo")) if display_tab == TAB_LOADING and loading_view == "month" else None
        archive_date = request.args.get("archive_date", "")
        if archive_date:
            return redirect(url_for("index", tab=display_tab, archive_date=archive_date, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        tab = get_station_idle_source_tab(idle_view) if display_tab == TAB_STATION_IDLE else get_source_tab(display_tab)
        try:
            # Try to load from folder first
            try:
                try_mail_sync(tab, force=False)
                return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
            except Exception as folder_error:
                # If folder loading fails and email is enabled, try email
                if email_enabled(tab) and get_imap_config(app.config["SETTINGS"], tab).get("check_on_refresh"):
                    try_mail_sync(tab, force=False)
                    return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
                else:
                    # Re-raise folder error if no email fallback
                    raise folder_error
        except Exception as exc:
            set_error(f"Не удалось обновить из папки: {exc}")
            return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        state = get_state(tab)
        if state and state.file_path and Path(state.file_path).exists():
            try:
                load_from_path(state.file_path, mode=tab, source_name=state.source_name, source_kind=state.source_kind)
            except Exception as exc:
                set_error(f"Не удалось обновить справку: {exc}")
            return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        try:
            restored_state = load_latest_local_source(tab)
            if restored_state is not None:
                set_success(f"Загружена последняя сохранённая справка для вкладки «{TAB_LABELS[tab]}».")
                return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        except Exception as exc:
            set_error(f"Не удалось открыть последнюю сохранённую справку: {exc}")
            return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))
        set_error("Нет ранее загруженного файла для обновления.")
        return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))

    @app.route("/mail-sync")
    def mail_sync():
        display_tab = get_tab_name(request.args.get("tab"))
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view")) if display_tab == TAB_LOADING else "today"
        loading_month = normalize_month_key(request.args.get("loading_month")) if display_tab == TAB_LOADING and loading_view == "month" else None
        selected_cargo = normalize_spaces(request.args.get("selected_cargo")) if display_tab == TAB_LOADING and loading_view == "month" else None
        tab = get_station_idle_source_tab(idle_view) if display_tab == TAB_STATION_IDLE else get_source_tab(display_tab)
        try:
            try_mail_sync(tab, force=False)
        except Exception as exc:
            set_error(f"Не удалось получить Excel из почты: {exc}")
        return redirect(url_for("index", tab=display_tab, idle_view=idle_view, loading_view=loading_view if display_tab == TAB_LOADING else None, loading_month=loading_month, selected_cargo=selected_cargo))

    @app.route("/auto-sync")
    def auto_sync():
        display_tab = get_tab_name(request.args.get("tab"))
        idle_view = get_idle_view(request.args.get("idle_view"))
        tab = get_station_idle_source_tab(idle_view) if display_tab == TAB_STATION_IDLE else get_source_tab(display_tab)
        try:
            result = try_mail_sync(tab, force=False)
            return jsonify({"updated": bool(result), "enabled": True, "tab": display_tab})
        except Exception as exc:
            if not email_enabled(tab):
                return jsonify({"updated": False, "enabled": False, "tab": display_tab})
            return jsonify({"updated": False, "enabled": True, "tab": display_tab, "error": str(exc)})

    @app.route("/reload-last")
    def reload_last():
        display_tab = get_tab_name(request.args.get("tab"))
        idle_view = get_idle_view(request.args.get("idle_view"))
        return redirect(url_for("refresh", tab=display_tab, idle_view=idle_view))

    @app.route("/load-sample")
    def load_sample():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        idle_view = get_idle_view(request.args.get("idle_view"))
        source_tab = get_station_idle_source_tab(idle_view) if tab == TAB_STATION_IDLE else get_source_tab(tab)
        if source_tab != TAB_APPROACH:
            set_error("Демо-файл предусмотрен только для вкладки «Подход вагонов».")
            return redirect(url_for("index", tab=tab, idle_view=idle_view))
        default_path = app.config.get("DEFAULT_EXCEL")
        if default_path and Path(default_path).exists():
            try:
                load_from_path(default_path, mode=TAB_APPROACH, source_name=Path(default_path).name)
                set_success("Демо-файл загружен")
            except Exception as exc:
                set_error(f"Не удалось загрузить демо-файл: {exc}")
        else:
            set_error("Демо-файл не найден.")
        return redirect(url_for("index", tab=tab))

    @app.route("/export/summary")
    def export_summary():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            set_error("Нет данных для выгрузки.")
            return redirect(url_for("index", tab=tab, idle_view=idle_view, loading_view=loading_view if tab == TAB_LOADING else None))
        if tab == TAB_STATION_IDLE:
            if idle_view == "destination":
                summary_df = build_station_destination_idle_frame(state.df, state.report_dt)
            else:
                summary_df = build_station_idle_frame(state.df, state.report_dt)
            detail_df = detail_export_frame(filter_detail(state.df, report_dt=state.report_dt, idle_mode=idle_view))
        elif tab == TAB_RAW_MATERIAL:
            raw_df = filter_raw_material_idle(state.df, state.report_dt)
            summary_df = build_raw_material_idle_frame(state.df, state.report_dt)
            detail_df = detail_export_frame(filter_detail(raw_df, report_dt=state.report_dt))
        elif tab == TAB_LOADING:
            if loading_view == "month":
                set_error("Для вкладки «Погрузка с начала месяца» сводная выгрузка пока не предусмотрена.")
                return redirect(url_for("index", tab=tab, loading_view="month", loading_month=normalize_month_key(request.args.get("loading_month"), state.report_dt), selected_cargo=normalize_spaces(request.args.get("selected_cargo"))))
            loading_df = filter_loading_view(state.df, state.report_dt, loading_view)
            summary_df = build_summary_frame(loading_df)
            detail_df = detail_export_frame(filter_detail(loading_df, report_dt=state.report_dt))
        else:
            source_df = state.df
            if tab == TAB_APPROACH:
                source_df = _apply_approach_header_filters(
                    source_df,
                    normalize_spaces(request.args.get("approach_cargo_filter")),
                    normalize_spaces(request.args.get("approach_previous_cargo_filter")),
                )
            summary_source = filter_primary_destination(source_df) if tab == TAB_APPROACH else source_df
            summary_df = build_summary_frame(summary_source)
            detail_source = filter_detail(source_df, report_dt=state.report_dt, primary_destination_only=(tab == TAB_APPROACH))
            detail_df = detail_export_frame(detail_source)
        download_name = f"asu_podhod_summary_{tab}_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_temp_excel(lambda temp_path: write_excel_report(summary_df, detail_df, str(temp_path)), download_name)

    def send_temp_excel(build_file, download_name: str):
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                temp_path = Path(tmp.name)
            build_file(temp_path)
            payload = temp_path.read_bytes()
            return send_file(
                BytesIO(payload),
                as_attachment=True,
                download_name=download_name,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        finally:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass


    mailing_report_labels = _sync_mailing_report_registry()

    mailing_scheduler = MailingScheduler(
        storage=mailing_storage,
        report_registry=mailing_registry,
        mail_sender=mailing_sender,
        app=app,
        poll_interval_seconds=MAILING_POLL_INTERVAL_SECONDS,
    )
    try:
        if os.environ.get("WERKZEUG_RUN_MAIN") in {None, "true", "True", "1"}:
            mailing_scheduler.start()
    except Exception:
        pass

    def parse_detail_filters():
        road = request.args.get("road") or None
        station = request.args.get("station") or None
        kind = request.args.get("kind") or None
        cargo = request.args.get("cargo") or None
        wagon = request.args.get("wagon") or None
        destination = request.args.get("destination") or None
        origin = request.args.get("origin") or None
        train_index = request.args.get("train_index") or None
        trip_start = request.args.get("trip_start") or None
        formed_trains = (request.args.get("formed_trains") or "").strip() in {"1", "true", "True"}
        overdue_delivery = (request.args.get("overdue") or "").strip() in {"1", "true", "True"}
        primary_only = (request.args.get("primary_only") or "").strip() in {"1", "true", "True"}
        idle_bucket = request.args.get("idle_bucket") or None
        idle_view = get_idle_view(request.args.get("idle_view"))
        exclude_ugleuralskaya = (request.args.get("exclude_ugleuralskaya") or "").strip() in {"1", "true", "True"}
        raw_material_cargo = normalize_spaces(request.args.get("raw_material_cargo")) or None
        cargo_name_filter = normalize_spaces(request.args.get("cargo_name_filter")) or None
        trip_end_date = (request.args.get("trip_end_date") or "").strip() or None
        departure_acceptance_date = (request.args.get("departure_acceptance_date") or "").strip() or None
        raw_material_days_raw = (request.args.get("raw_material_days") or "").strip()
        if raw_material_days_raw.isdigit():
            raw_material_days = int(raw_material_days_raw)
        elif raw_material_days_raw.lower() == RAW_MATERIAL_IDLE_OVERFLOW_FILTER:
            raw_material_days = RAW_MATERIAL_IDLE_OVERFLOW_FILTER
        else:
            raw_material_days = None
        return road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, idle_view, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date

    def _parse_filtered_rows_payload(raw_payload: object, expected_columns: list[str] | None = None) -> pd.DataFrame | None:
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
            frame = pd.DataFrame(columns=expected_columns or None)
        if expected_columns:
            for column in expected_columns:
                if column not in frame.columns:
                    frame[column] = ""
            frame = frame[expected_columns]
        return frame.fillna("")

    def build_map_query_payload(
        tab: str,
        archive_date: str,
        idle_view: str,
        loading_view: str,
        road: Optional[str],
        station: Optional[str],
        kind: Optional[str],
        cargo: Optional[str],
        wagon: Optional[str],
        destination: Optional[str],
        origin: Optional[str],
        train_index: Optional[str],
        trip_start: Optional[str],
        formed_trains: bool,
        overdue_delivery: bool,
        primary_only: bool,
        idle_bucket: Optional[str],
        raw_material_cargo: Optional[str] = None,
        raw_material_days: Optional[int] = None,
        cargo_name_filter: Optional[str] = None,
        trip_end_date: Optional[str] = None,
        departure_acceptance_date: Optional[str] = None,
    ) -> dict:
        return {
            k: v
            for k, v in {
                "tab": tab,
                "archive_date": archive_date or None,
                "idle_view": idle_view if tab == TAB_STATION_IDLE else None,
                "loading_view": loading_view if tab == TAB_LOADING else None,
                "road": road,
                "station": station,
                "kind": kind,
                "cargo": cargo,
                "destination": destination,
                "origin": origin,
                "train_index": train_index,
                "trip_start": trip_start,
                "wagon": wagon,
                "formed_trains": "1" if formed_trains else None,
                "overdue": "1" if overdue_delivery else None,
                "primary_only": "1" if primary_only else None,
                "idle_bucket": idle_bucket,
                "raw_material_cargo": raw_material_cargo,
                "raw_material_days": str(raw_material_days) if raw_material_days is not None else None,
                "cargo_name_filter": cargo_name_filter,
                "trip_end_date": trip_end_date,
                "departure_acceptance_date": departure_acceptance_date,
                "approach_cargo_filter": normalize_spaces(request.args.get("approach_cargo_filter")) if tab == TAB_APPROACH else None,
                "approach_previous_cargo_filter": normalize_spaces(request.args.get("approach_previous_cargo_filter")) if tab == TAB_APPROACH else None,
            }.items()
            if v
        }

    @app.route("/export/detail", methods=["GET", "POST"])
    def export_detail():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            set_error("Нет данных для выгрузки.")
            return redirect(url_for("index", tab=tab, idle_view=idle_view))
        road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, idle_view, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date = parse_detail_filters()
        effective_kind = kind
        if tab == TAB_APPROACH and _is_approach_direction(origin) and not effective_kind:
            effective_kind = "ЦС"
        loading_view = get_loading_view(request.values.get("loading_view"))
        export_df = _parse_filtered_rows_payload(request.form.get("filtered_rows"), list(detail_export_frame(pd.DataFrame()).columns)) if request.method == "POST" else None
        if export_df is None:
            df = _build_filtered_view(
                tab, state, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date
            )
            export_df = detail_export_frame(df)
        download_name = build_detail_download_name(tab, idle_view, loading_view, raw=False)

        def _build_detail_export(temp_path: Path) -> None:
            write_single_sheet_excel(export_df, str(temp_path), sheet_name="Пономерной список")

        return send_temp_excel(_build_detail_export, download_name)

    @app.route("/export/raw")
    def export_raw():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            set_error("Нет данных для выгрузки.")
            return redirect(url_for("index", tab=tab, idle_view=idle_view))
        road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, idle_view, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date = parse_detail_filters()
        effective_kind = kind
        if tab == TAB_APPROACH and _is_approach_direction(origin) and not effective_kind:
            effective_kind = "ЦС"
        loading_view = get_loading_view(request.args.get("loading_view"))
        raw_df = _build_filtered_view(
            tab, state, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date
        ).copy()
        drop_cols = [col for col in ["__sort_dt"] if col in raw_df.columns]
        if drop_cols:
            raw_df = raw_df.drop(columns=drop_cols)
        download_name = build_detail_download_name(tab, idle_view, loading_view, raw=True)

        def _build_raw_export(temp_path: Path) -> None:
            write_single_sheet_excel(raw_df, str(temp_path), sheet_name="Исходные данные")

        return send_temp_excel(_build_raw_export, download_name)

    @app.route("/details")
    def details():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            return redirect(
                url_for(
                    "index",
                    tab=tab,
                    idle_view=idle_view,
                    loading_view=loading_view if tab == TAB_LOADING else None,
                )
            )

        road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, idle_view, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date = parse_detail_filters()
        effective_kind = kind
        if tab == TAB_APPROACH and _is_approach_direction(origin) and not effective_kind:
            effective_kind = "ЦС"

        df = _build_filtered_view(
            tab, state, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date
        )

        card_only_view = is_card_only_view(tab, destination, origin, train_index, trip_start)
        train_rows = build_train_presentation_rows(df, include_weight=(tab == TAB_DEPARTURE)) if card_only_view else []

        if card_only_view:
            base_payload = {
                k: v
                for k, v in {
                    "tab": tab,
                    "archive_date": archive_date or None,
                    "road": road,
                    "station": station,
                    "kind": kind,
                    "cargo": cargo,
                    "destination": destination,
                    "origin": origin,
                    "formed_trains": "1" if formed_trains else None,
                    "overdue": "1" if overdue_delivery else None,
                    "primary_only": "1" if primary_only else None,
                    "idle_view": idle_view if tab == TAB_STATION_IDLE else None,
                    "loading_view": loading_view if tab == TAB_LOADING else None,
                }.items()
                if v
            }
            for row in train_rows:
                detail_train_index = row.get("train_index_normalized", "")
                detail_trip_start = row.get("trip_start_filter", "")
                detail_payload = dict(base_payload)
                if detail_train_index:
                    detail_payload["train_index"] = detail_train_index
                elif detail_trip_start:
                    detail_payload["trip_start"] = detail_trip_start
                    if row.get("detail_origin") and not detail_payload.get("origin"):
                        detail_payload["origin"] = row.get("detail_origin", "")
                row["detail_link"] = (
                    url_for("details") + "?" + urlencode(detail_payload)
                    if detail_train_index or detail_trip_start
                    else None
                )

        show_detail_table = not card_only_view

        records = []
        if show_detail_table:
            for _, row in df.iterrows():
                arrival_destination_value = row.get("arrival_destination_display", "")
                if not normalize_spaces(arrival_destination_value):
                    arrival_destination_value = row.get("Дата и время прибытия (АСОУП) на станцию назначения", "")

                records.append(
                    {
                        "wagon_number": row.get("Номер вагона", ""),
                        "raw_kind": strip_last_numeric_code(row.get("Род вагона", "")),
                        "trip_start": row.get("Дата и время начала рейса", ""),
                        "trip_end": row.get("Дата и время окончания рейса", ""),
                        "origin_road": row.get("Дорога отправления", ""),
                        "origin_station": row.get("Станция отправления", ""),
                        "destination_road": row.get("Дорога назначения", ""),
                        "destination": row.get("Станция назначения", ""),
                        "shipper": row.get("Грузоотправитель", row.get("Грузоотправитель (наим)", "")),
                        "cargo_name": row.get("raw_material_cargo_name", "") if tab == TAB_RAW_MATERIAL else row.get("Наименование груза", ""),
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
                )

        wagon_search_summary = build_wagon_search_summary(wagon, records) if show_detail_table else None
        exact_wagon_display = wagon if not wagon_search_summary else None

        caption_parts = []
        if wagon_search_summary:
            caption_parts.append("Поиск по номерам вагонов")
        if formed_trains:
            caption_parts.append("Сформированные поезда")
        if overdue_delivery:
            caption_parts.append("Вагоны с нарушенным сроком доставки")
        if destination:
            caption_parts.append(f"Назначение {destination}")
        if origin:
            caption_parts.append(f"Отправление {origin}")
        if train_index:
            caption_parts.append(f"Поезд {train_index}")
        if trip_start:
            caption_parts.append(f"Начало рейса {trip_start}")
        if wagon and not wagon_search_summary:
            caption_parts.append(f"Вагон {wagon}")
        if raw_material_cargo:
            caption_parts.append(f"Груз {raw_material_cargo}")
        if cargo_name_filter:
            caption_parts.append(f"Груз {cargo_name_filter}")
        if raw_material_days is not None:
            caption_parts.append(raw_material_idle_label(raw_material_days))
        if trip_end_date:
            caption_parts.append(f"Дата окончания рейса {_format_filter_date_label(trip_end_date)}")
        if departure_acceptance_date:
            caption_parts.append(f"Отправлено со станции приёма {_format_filter_date_label(departure_acceptance_date)}")
        if road:
            caption_parts.append(road)
        if station:
            caption_parts.append(station)
        if kind:
            caption_parts.append(kind)
        if cargo == "гр":
            caption_parts.append("Гружёные")
        elif cargo == "пор":
            caption_parts.append("Порожние")
        filter_caption = " / ".join(caption_parts) if caption_parts else "Все вагоны"

        query_payload = build_map_query_payload(
            tab, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date
        )

        export_link = url_for("export_detail") + ("?" + urlencode(query_payload) if query_payload else "")
        raw_export_link = url_for("export_raw") + ("?" + urlencode(query_payload) if query_payload else "")

        cargo_label = None
        if cargo == "гр":
            cargo_label = "Гружёные"
        elif cargo == "пор":
            cargo_label = "Порожние"

        total_count = len(records) if show_detail_table else count_train_card_wagons(train_rows)

        destination_cargo_summary = []
        destination_cargo_summary_title = ""
        destination_cargo_reset_link = None
        destination_cargo_total = 0
        destination_cargo_unique_count = 0
        if tab == TAB_STATION_IDLE and idle_view == "destination" and station:
            station_scope_df = _build_filtered_view(
                tab, state, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, None, None, None
            )
            if not station_scope_df.empty:
                cargo_series = station_scope_df.get("Наименование груза", pd.Series("", index=station_scope_df.index)).fillna("").astype(str).map(normalize_spaces)
                cargo_series = cargo_series.where(cargo_series != "", "Без указания")
                cargo_counts = cargo_series.value_counts()
                current_cargo_name = normalize_spaces(cargo_name_filter)
                destination_cargo_summary = [
                    {
                        "cargo_name": cargo_name,
                        "count": int(count),
                        "is_active": current_cargo_name == normalize_spaces(cargo_name),
                        "link": build_link(
                            tab=tab,
                            road=road,
                            station=station,
                            kind=kind,
                            cargo=cargo,
                            exact_wagon=wagon,
                            formed_trains=formed_trains,
                            destination=destination,
                            origin=origin,
                            train_index=train_index,
                            trip_start=trip_start,
                            overdue_delivery=overdue_delivery,
                            primary_only=primary_only,
                            idle_bucket=idle_bucket,
                            idle_view=idle_view,
                            archive_date=archive_date,
                            cargo_name_filter=cargo_name,
                        ) if current_cargo_name != normalize_spaces(cargo_name) else None,
                    }
                    for cargo_name, count in cargo_counts.items()
                ]
                destination_cargo_summary_title = f"Станция: {station}"
                destination_cargo_total = int(cargo_counts.sum())
                destination_cargo_unique_count = int(len(cargo_counts))
                if current_cargo_name:
                    destination_cargo_reset_link = build_link(
                        tab=tab,
                        road=road,
                        station=station,
                        kind=kind,
                        cargo=cargo,
                        exact_wagon=wagon,
                        formed_trains=formed_trains,
                        destination=destination,
                        origin=origin,
                        train_index=train_index,
                        trip_start=trip_start,
                        overdue_delivery=overdue_delivery,
                        primary_only=primary_only,
                        idle_bucket=idle_bucket,
                        idle_view=idle_view,
                        archive_date=archive_date,
                    )

        detail_html = render_page(
            DETAIL_BODY,
            title=f"{APP_TITLE} — детали",
            current_tab=tab,
            current_tab_label=TAB_LABELS[tab],
            road=road,
            station=station,
            kind=effective_kind,
            destination_label=destination,
            origin_label=origin,
            train_index_label=train_index,
            overdue_label="Нарушенный ср. дст." if overdue_delivery else None,
            cargo_label=cargo_label,
            raw_material_cargo_label=raw_material_cargo,
            raw_material_idle_label=raw_material_idle_label(raw_material_days) if raw_material_days is not None else None,
            idle_bucket_label=(f"Груз: {cargo_name_filter}" if cargo_name_filter else None),
            formed_trains_label="Сформированные поезда" if formed_trains else None,
            exact_wagon=exact_wagon_display,
            wagon_search_summary=wagon_search_summary,
            total_count=total_count,
            records=records,
            train_rows=train_rows,
            show_detail_table=show_detail_table,
            filter_caption=filter_caption,
            export_link=export_link,
            raw_export_link=raw_export_link,
            loading_mode=loading_view,
            destination_cargo_summary=destination_cargo_summary,
            destination_cargo_summary_title=destination_cargo_summary_title,
            destination_cargo_reset_link=destination_cargo_reset_link,
            destination_cargo_total=destination_cargo_total,
            destination_cargo_unique_count=destination_cargo_unique_count,
        )
        return _inject_detail_row_highlight(detail_html)

    @app.route("/station-map")
    def station_map():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        archive_date = request.args.get("archive_date", "")
        idle_view = get_idle_view(request.args.get("idle_view"))
        loading_view = get_loading_view(request.args.get("loading_view"))
        state = get_display_state(tab, archive_date, idle_view)
        if state is None:
            return redirect(url_for("index", tab=tab, archive_date=archive_date, idle_view=idle_view if tab == TAB_STATION_IDLE else None, loading_view=loading_view if tab == TAB_LOADING else None))

        road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, idle_view, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date = parse_detail_filters()
        filtered_df = _build_filtered_view(
            tab, state, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, exclude_ugleuralskaya, raw_material_cargo, raw_material_days, cargo_name_filter, trip_end_date, departure_acceptance_date
        )
        points, unresolved_stations = build_map_points(filtered_df)
        filter_caption_parts = []
        if destination:
            filter_caption_parts.append(f"Станция назначения: {destination}")
        if origin:
            filter_caption_parts.append(f"Станция отправления: {origin}")
        if road:
            filter_caption_parts.append(f"Дорога: {road}")
        if station:
            filter_caption_parts.append(f"Станция строки: {station}")
        if kind and kind != "Всего":
            filter_caption_parts.append(kind)
        if cargo == "гр":
            filter_caption_parts.append("Гружёные")
        elif cargo == "пор":
            filter_caption_parts.append("Порожние")
        if idle_bucket:
            filter_caption_parts.append(f"Интервал: {idle_bucket}")
        filter_caption = " • ".join(filter_caption_parts) if filter_caption_parts else "Все вагоны выбранной строки"

        query_payload = build_map_query_payload(
            tab, archive_date, idle_view, loading_view, road, station, kind, cargo, wagon, destination, origin, train_index, trip_start, formed_trains, overdue_delivery, primary_only, idle_bucket, raw_material_cargo, raw_material_days, cargo_name_filter
        )
        back_url = url_for("index") + ("?" + urlencode({k: v for k, v in query_payload.items() if k not in {"kind", "cargo", "wagon", "train_index", "trip_start", "formed_trains", "overdue", "primary_only", "idle_bucket"}}) if query_payload else "")
        export_link = url_for("export_detail") + ("?" + urlencode(query_payload) if query_payload else "")
        raw_export_link = url_for("export_raw") + ("?" + urlencode(query_payload) if query_payload else "")

        station_directory = load_station_directory()
        return render_page(
            MAP_BODY,
            title=f"{APP_TITLE} — карта вагонов",
            app_title=APP_TITLE,
            current_tab=tab,
            current_tab_label=TAB_LABELS[tab],
            archive_date=archive_date,
            idle_view=idle_view,
            loading_mode=loading_view,
            filter_caption=filter_caption,
            map_points=points,
            map_points_json=json.dumps(points, ensure_ascii=False),
            unresolved_stations=unresolved_stations[:50],
            total_wagons=int(len(filtered_df.index)),
            back_url=back_url,
            export_link=export_link,
            raw_export_link=raw_export_link,
            station_directory_available=bool(station_directory.get("available")),
            station_directory_path=station_directory.get("path"),
            selected_station=get_selected_station_name(),
            destination_keyword=get_selected_station_name() or DEFAULT_WORK_STATION,
            error_message=pop_error(),
            success_message=pop_success(),
        )

    @app.route("/stop-rent/access", methods=["GET", "POST"])

    def stop_rent_access():
        tab = get_tab_name(request.values.get("tab"))
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return redirect(url_for("index", tab=tab))
        archive_date = request.values.get("archive_date", "")
        if request.method == "POST":
            password = (request.form.get("password") or "").strip()
            if verify_stop_rent_password(password):
                set_stop_rent_authenticated(tab, True)
                set_success("Доступ к разделу «Стоп аренда» разрешён.")
                return redirect(url_for("stop_rent", tab=tab, archive_date=archive_date))
            set_error("Неверный пароль.")
        security = load_stop_rent_security()
        return render_page(
            STOP_RENT_ACCESS_BODY,
            title=f"{APP_TITLE} — доступ к стоп аренде",
            current_tab=tab,
            archive_date=archive_date,
            failed_attempts=int(security.get("failed_attempts", 0) or 0),
            show_reset_button=int(security.get("failed_attempts", 0) or 0) >= 3,
            request_code=str(security.get("reset_request_code") or ""),
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/stop-rent/reset-request", methods=["POST"])
    def stop_rent_reset_request():
        tab = get_tab_name(request.values.get("tab"))
        archive_date = request.values.get("archive_date", "")
        security = load_stop_rent_security()
        if int(security.get("failed_attempts", 0) or 0) < 3:
            set_error("Кнопка сброса становится доступной после 3 неверных попыток.")
        else:
            issue_stop_rent_reset_request()
            set_success("Код запроса сформирован.")
        return redirect(url_for("stop_rent_access", tab=tab, archive_date=archive_date))

    @app.route("/stop-rent/reset-confirm", methods=["POST"])
    def stop_rent_reset_confirm():
        tab = get_tab_name(request.values.get("tab"))
        archive_date = request.values.get("archive_date", "")
        security = load_stop_rent_security()
        request_code = str(security.get("reset_request_code") or "")
        recovery_code = (request.form.get("recovery_code") or "").strip()
        new_password = (request.form.get("new_password") or "").strip()
        new_password_confirm = (request.form.get("new_password_confirm") or "").strip()
        if not request_code:
            set_error("Сначала сформируйте код запроса.")
        elif not new_password:
            set_error("Новый пароль не задан.")
        elif new_password != new_password_confirm:
            set_error("Новый пароль и подтверждение не совпадают.")
        else:
            ok, recovery_error = verify_stop_rent_recovery_code(request_code, recovery_code)
            if not ok:
                set_error(recovery_error or "Код восстановления неверный.")
            else:
                set_stop_rent_password(new_password)
                set_stop_rent_authenticated(tab, False)
                set_success("Пароль успешно сброшен и заменён новым.")
        return redirect(url_for("stop_rent_access", tab=tab, archive_date=archive_date))

    @app.route("/stop-rent/password", methods=["GET", "POST"])
    def stop_rent_password():
        tab = get_tab_name(request.values.get("tab"))
        archive_date = request.values.get("archive_date", "")
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return redirect(url_for("index", tab=tab))
        if not is_stop_rent_authenticated(tab):
            return redirect(url_for("stop_rent_access", tab=tab, archive_date=archive_date))
        if request.method == "POST":
            current_password = (request.form.get("current_password") or "").strip()
            new_password = (request.form.get("new_password") or "").strip()
            new_password_confirm = (request.form.get("new_password_confirm") or "").strip()
            security = load_stop_rent_security()
            if security.get("password_hash") != _password_hash(current_password):
                set_error("Текущий пароль введён неверно.")
            elif not new_password:
                set_error("Новый пароль не задан.")
            elif new_password != new_password_confirm:
                set_error("Новый пароль и подтверждение не совпадают.")
            else:
                set_stop_rent_password(new_password)
                set_success("Пароль раздела «Стоп аренда» обновлён.")
                return redirect(url_for("stop_rent", tab=tab, archive_date=archive_date))
        return render_page(
            STOP_RENT_PASSWORD_BODY,
            title=f"{APP_TITLE} — смена пароля",
            current_tab=tab,
            archive_date=archive_date,
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/stop-rent")
    def stop_rent():
        requested_tab = request.args.get("tab")
        if not requested_tab:
            requested_tab = load_ui_preferences().get("startup_tab") or TAB_DASHBOARD
        tab = get_tab_name(requested_tab)
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return redirect(url_for("index", tab=tab))
        archive_date = request.args.get("archive_date", "")
        if not is_stop_rent_authenticated(tab):
            return redirect(url_for("stop_rent_access", tab=tab, archive_date=archive_date))
        state = get_effective_state(tab, archive_date)
        if state is None:
            return redirect(url_for("index", tab=tab))
        station_options: list[dict] = []
        selected_station = request.args.get("station", "").strip()
        batch_id = request.args.get("batch", "").strip()
        station_records: list[dict] = []
        if not archive_date:
            available_df = filter_primary_destination(state.df) if tab == TAB_APPROACH else state.df
            for station_name in sorted(available_df["summary_station_display"].dropna().unique().tolist()):
                station_df = filter_detail(available_df, station=station_name)
                count_value = int(len(station_df))
                if count_value > 0:
                    station_options.append({"name": station_name, "count": count_value})
            if selected_station:
                station_df = filter_detail(available_df, station=selected_station)
                for _, row in station_df.iterrows():
                    station_records.append(
                        {
                            "wagon_number": normalize_wagon_number(row.get("Номер вагона", "")),
                            "raw_kind": strip_last_numeric_code(row.get("Род вагона", "")),
                            "operation": strip_last_numeric_code(row.get("Операция с вагоном", "")),
                            "operation_time": row.get("Дата и время операции", ""),
                        }
                    )
        stop_groups = get_stop_rent_groups(tab, state.report_dt)
        selected_group = get_stop_rent_group(tab, batch_id, state.report_dt) if batch_id else None
        stop_rent_total_count = sum(group.get("count", 0) for group in stop_groups)
        return render_page(
            STOP_RENT_BODY,
            title=f"{APP_TITLE} — стоп аренда",
            current_tab=tab,
            archive_date=archive_date,
            selected_station=selected_station,
            station_options=station_options,
            station_records=station_records,
            default_start_date=state.report_dt.date().isoformat(),
            stop_rent_groups=stop_groups,
            stop_rent_total_count=stop_rent_total_count,
            selected_group=selected_group,
            batch_id=batch_id,
            success_message=pop_success(),
            error_message=pop_error(),
        )

    @app.route("/stop-rent/create", methods=["POST"])
    def stop_rent_create():
        tab = get_tab_name(request.form.get("tab"))
        if tab not in {TAB_APPROACH, TAB_DEPARTURE}:
            return redirect(url_for("index", tab=tab))
        if not is_stop_rent_authenticated(tab):
            return redirect(url_for("stop_rent_access", tab=tab))
        archive_date = request.form.get("archive_date", "")
        if archive_date:
            set_error("В архивном режиме создание стоп аренды недоступно.")
            return redirect(url_for("stop_rent", tab=tab, archive_date=archive_date))
        station = (request.form.get("station") or "").strip()
        start_date = (request.form.get("start_date") or "").strip()
        wagon_numbers = request.form.getlist("wagon_numbers")
        if not station:
            set_error("Не выбрана станция.")
            return redirect(url_for("stop_rent", tab=tab))
        if not start_date:
            set_error("Не выбрана дата начала стоп аренды.")
            return redirect(url_for("stop_rent", tab=tab, station=station))
        if not wagon_numbers:
            set_error("Не выбраны вагоны.")
            return redirect(url_for("stop_rent", tab=tab, station=station))
        state = get_effective_state(tab, "")
        station_rows: dict[str, dict] = {}
        if state is not None:
            available_df = filter_primary_destination(state.df) if tab == TAB_APPROACH else state.df
            station_df = filter_detail(available_df, station=station)
            for _, row in station_df.iterrows():
                station_rows[normalize_wagon_number(row.get("Номер вагона", ""))] = row.to_dict()
        created = create_stop_rent_records(tab, station, wagon_numbers, start_date, station_rows)
        if created:
            set_success(f"Стоп аренда сохранена: {created} ваг.")
        else:
            set_error("Новые записи не добавлены: выбранные вагоны уже находятся в стоп аренде.")
        return redirect(url_for("stop_rent", tab=tab, station=station))

    @app.route("/stop-rent/delete-selected", methods=["POST"])
    def stop_rent_delete_selected():
        tab = get_tab_name(request.form.get("tab"))
        if not is_stop_rent_authenticated(tab):
            return redirect(url_for("stop_rent_access", tab=tab))
        batch_id = (request.form.get("batch_id") or "").strip()
        wagon_numbers = request.form.getlist("wagon_numbers")
        removed = remove_stop_rent_selected(tab, batch_id, wagon_numbers)
        if removed:
            set_success(f"Удалено из стоп аренды: {removed} ваг.")
        else:
            set_error("Не выбраны вагоны для удаления.")
        return redirect(url_for("stop_rent", tab=tab, batch=batch_id))

    @app.route("/stop-rent/delete-batch", methods=["POST"])
    def stop_rent_delete_batch():
        tab = get_tab_name(request.form.get("tab"))
        if not is_stop_rent_authenticated(tab):
            return redirect(url_for("stop_rent_access", tab=tab))
        batch_id = (request.form.get("batch_id") or "").strip()
        removed = remove_stop_rent_batch(tab, batch_id)
        if removed:
            set_success(f"Удалена группа стоп аренды: {removed} ваг.")
        else:
            set_error("Группа для удаления не найдена.")
        return redirect(url_for("stop_rent", tab=tab))


    def _render_mailing_form(rule: MailingRule, page_title: str):
        report_options = _mailing_report_options()
        report_labels = _sync_mailing_report_registry()
        current_report_type = _normalize_manual_text(rule.report_type)
        if current_report_type and all(item["value"] != current_report_type for item in report_options):
            manual_filter_name = _parse_manual_mailing_report_name(current_report_type) or _normalize_manual_text(getattr(rule, "manual_filter_name", ""))
            if manual_filter_name:
                report_options.append({"value": current_report_type, "label": _manual_mailing_label(manual_filter_name)})
                report_labels[current_report_type] = _manual_mailing_label(manual_filter_name)
        return render_page(
            MAILING_FORM_BODY,
            title=f"{APP_TITLE} — {page_title}",
            current_tab=TAB_MAILING,
            page_title=page_title,
            rule=rule,
            report_options=report_options,
            report_labels=report_labels,
            schedule_options=_mailing_schedule_options(),
            weekday_options=_mailing_weekday_options(),
            selected_weekdays=set(rule.normalized_weekdays()),
            times_text=", ".join(rule.normalized_times()),
            error_message=pop_error(),
            success_message=pop_success(),
        )

    @app.route("/mailing")
    def mailing_rules():
        rules = mailing_storage.list_rules()
        schedule_map = {rule.id: describe_schedule(rule) for rule in rules if rule.id is not None}
        return render_page(
            MAILING_BODY,
            title=f"{APP_TITLE} — авторассылка справок",
            current_tab=TAB_MAILING,
            rules=rules,
            schedule_map=schedule_map,
            report_labels=_sync_mailing_report_registry(),
            error_message=pop_error(),
            success_message=pop_success(),
        )

    @app.route("/mailing/new", methods=["GET", "POST"])
    def mailing_new():
        rule = MailingRule(
            enabled=True,
            subject="",
            body="Во вложении актуальная справка.",
            attach_filename_template="{report_label}_{date}.xlsx",
        )
        if request.method == "POST":
            rule = _mailing_form_rule(rule)
            error_text = _validate_mailing_rule(rule)
            if error_text:
                set_error(error_text)
                return _render_mailing_form(rule, "Новая рассылка")
            _sync_mailing_report_registry()
            mailing_storage.insert_rule(rule)
            set_success("Правило авторассылки сохранено.")
            return redirect(url_for("mailing_rules"))
        return _render_mailing_form(rule, "Новая рассылка")

    @app.route("/mailing/edit/<int:rule_id>", methods=["GET", "POST"])
    def mailing_edit(rule_id: int):
        rule = mailing_storage.get_rule(rule_id)
        if rule is None:
            set_error("Правило авторассылки не найдено.")
            return redirect(url_for("mailing_rules"))
        if request.method == "POST":
            updated_rule = _mailing_form_rule(rule)
            error_text = _validate_mailing_rule(updated_rule)
            if error_text:
                set_error(error_text)
                return _render_mailing_form(updated_rule, "Редактирование рассылки")
            _sync_mailing_report_registry()
            mailing_storage.update_rule(updated_rule)
            set_success("Правило авторассылки обновлено.")
            return redirect(url_for("mailing_rules"))
        return _render_mailing_form(rule, "Редактирование рассылки")

    @app.route("/mailing/delete/<int:rule_id>", methods=["POST"])
    def mailing_delete(rule_id: int):
        rule = mailing_storage.get_rule(rule_id)
        if rule is None:
            set_error("Правило авторассылки не найдено.")
        else:
            mailing_storage.delete_rule(rule_id)
            set_success(f"Правило «{rule.name}» удалено.")
        return redirect(url_for("mailing_rules"))

    @app.route("/mailing/toggle/<int:rule_id>", methods=["POST"])
    def mailing_toggle(rule_id: int):
        rule = mailing_storage.get_rule(rule_id)
        if rule is None:
            set_error("Правило авторассылки не найдено.")
        else:
            mailing_storage.set_rule_enabled(rule_id, not rule.enabled)
            set_success(f"Правило «{rule.name}» {'включено' if not rule.enabled else 'отключено'}.")
        return redirect(url_for("mailing_rules"))

    @app.route("/mailing/send-now/<int:rule_id>", methods=["POST"])
    def mailing_send_now(rule_id: int):
        rule = mailing_storage.get_rule(rule_id)
        if rule is None:
            set_error("Правило авторассылки не найдено.")
            return redirect(url_for("mailing_rules"))
        sent = mailing_scheduler.send_rule_now(rule_id, slot_key=f"manual-{now().strftime('%Y-%m-%d %H:%M:%S')}")
        if sent:
            set_success(f"Справка по правилу «{rule.name}» отправлена.")
        else:
            refreshed_rule = mailing_storage.get_rule(rule_id)
            error_text = (refreshed_rule.last_error if refreshed_rule else "") or "Отправка не выполнена."
            set_error(error_text)
        return redirect(url_for("mailing_rules"))

    @app.route("/mailing/logs")
    def mailing_logs():
        logs = mailing_storage.list_logs(limit=200)
        return render_page(
            MAILING_LOGS_BODY,
            title=f"{APP_TITLE} — журнал авторассылки",
            current_tab=TAB_MAILING,
            logs=logs,
            report_labels=_sync_mailing_report_registry(),
            error_message=pop_error(),
            success_message=pop_success(),
        )

    @app.route("/api/gu23/wagons/lookup", methods=["POST"])
    def api_gu23_wagons_lookup():
        payload = request.get_json(silent=True) or {}
        raw_numbers = payload.get("wagon_numbers") or []
        if not isinstance(raw_numbers, list):
            return jsonify({"error": "Поле wagon_numbers должно быть массивом."}), 400

        requested: list[str] = []
        seen_requested: set[str] = set()
        for value in raw_numbers:
            wagon_number = normalize_wagon_number(value)
            if wagon_number and wagon_number not in seen_requested:
                seen_requested.add(wagon_number)
                requested.append(wagon_number)

        if not requested:
            return jsonify({"error": "Не переданы корректные номера вагонов."}), 400

        source_tabs = [TAB_APPROACH, TAB_DEPARTURE]
        ready_states: list[tuple[str, SourceState]] = []
        warnings: list[str] = []
        for source_tab in source_tabs:
            state = get_state(source_tab)
            if state is None:
                state = ensure_loaded(source_tab)
            if state is None:
                warnings.append(f"Не загружена справка для вкладки '{TAB_LABELS.get(source_tab, source_tab)}'.")
                continue
            ready_states.append((source_tab, state))

        if not ready_states:
            return jsonify({"requested": requested, "found": [], "not_found": requested, "warnings": warnings}), 409

        found_by_wagon: dict[str, dict] = {}
        for source_tab, state in ready_states:
            df = state.df.copy()
            if df is None or df.empty or "Номер вагона" not in df.columns:
                continue
            if "Станция операции" not in df.columns:
                continue
            df = df[df["Станция операции"].map(is_ugleuralskaya_station)].copy()
            if df.empty:
                continue
            if "__sort_dt" in df.columns:
                df = df.sort_values("__sort_dt", ascending=False, na_position="last")

            requested_set = set(requested)
            for _, row in df.iterrows():
                wagon_number = normalize_wagon_number(row.get("Номер вагона", ""))
                if not wagon_number or wagon_number not in requested_set:
                    continue
                report_dt = state.report_dt or now()
                current = found_by_wagon.get(wagon_number)
                if current is not None:
                    current_report_dt = current.get("_report_dt") or datetime.min
                    if report_dt <= current_report_dt:
                        continue
                found_by_wagon[wagon_number] = {
                    "wagon_number": wagon_number,
                    "owner": str(row.get("owner_display", "") or row.get("Собственник", "") or "").strip(),
                    "wagon_kind": strip_last_numeric_code(row.get("Род вагона", "")),
                    "origin_station": str(row.get("origin_station_display", "") or row.get("Станция отправления", "") or "").strip(),
                    "destination_station": str(row.get("destination_display", "") or row.get("Станция назначения", "") or "").strip(),
                    "source_tab": source_tab,
                    "report_datetime": report_dt.strftime("%d.%m.%Y %H:%M") if isinstance(report_dt, datetime) else "",
                    "_report_dt": report_dt,
                }

        found: list[dict] = []
        not_found: list[str] = []
        for wagon_number in requested:
            item = found_by_wagon.get(wagon_number)
            if item is None:
                not_found.append(wagon_number)
                continue
            item = dict(item)
            item.pop("_report_dt", None)
            found.append(item)

        return jsonify({"requested": requested, "found": found, "not_found": not_found, "warnings": warnings})


    archive_index = prune_archive(load_archive_index())
    save_archive_index(archive_index)
    register_idle_comments_routes(
        app,
        get_approach_state=get_approach_state,
        now_func=now,
        set_success=set_success,
        pop_success=pop_success,
        set_error=set_error,
        pop_error=pop_error,
    )
    register_technical_state_routes(
        app,
        get_approach_state=get_approach_state,
        get_departure_state=get_departure_state,
        now_func=now,
        set_error=set_error,
        pop_error=pop_error,
        pop_success=pop_success,
    )
    register_claims_ugleuralskaya_routes(
        app,
        get_approach_state=get_approach_state,
        get_departure_state=get_departure_state,
        get_archived_state=get_archived_state,
        list_archived_dates=list_archived_dates,
        now_func=now,
        set_success=set_success,
        pop_success=pop_success,
        set_error=set_error,
        pop_error=pop_error,
    )

    try:
        if os.environ.get("WERKZEUG_RUN_MAIN") in {None, "true", "True", "1"}:
            _start_mail_autoupdate_scheduler()
    except Exception:
        pass

    return app
