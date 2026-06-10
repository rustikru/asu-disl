from __future__ import annotations

import os
from pathlib import Path

APP_TITLE = "АСУ Подход"
APP_VERSION = "1.0.0"

SETTINGS_FILE = "settings.json"
LICENSE_SETTINGS_FILE = "license_settings.json"

ARCHIVE_METADATA_FILE = "archive_metadata.json"
STOP_RENT_FILE = "stop_rent.json"
STOP_RENT_SECURITY_FILE = "stop_rent_security.json"
MAILING_DB_FILE = "mailing.db"
MANUAL_FILTERS_FILE = "manual_filters.json"
STATION_DIRECTORY_FILE = "asu_podhod_station_directory.json"
MAILING_POLL_INTERVAL_SECONDS = 60

TAB_APPROACH = "approach"
TAB_DEPARTURE = "departure"
TAB_STATION_IDLE = "station_idle"
TAB_LOADING = "loading"
TAB_RAW_MATERIAL = "raw_material"
TAB_MANUAL = "manual_filter"
TAB_MAILING = "mailing"
TAB_ARCHIVE = "archive"

TAB_LABELS = {
    TAB_APPROACH: "Подход вагонов",
    TAB_DEPARTURE: "Отправление вагонов",
    TAB_LOADING: "Погрузка",
    TAB_STATION_IDLE: "Простои",
    TAB_RAW_MATERIAL: "Сырье",
    TAB_MANUAL: "Ручной фильтр",
    TAB_MAILING: "Авторассылка справок",
    TAB_ARCHIVE: "Архив",
}

DEPARTURE_DESTINATION_CARDS = ["Ейск", "Забайкальск", "Лужская"]
APPROACH_ORIGIN_CARDS = ["Ейск", "Забайкальск"]

DEFAULT_IMAP_BLOCK = {
    "enabled": False,
    "server": "imap.gmail.com",
    "port": 993,
    "username": "",
    "password": "",
    "mailbox": "INBOX",
    "sender_filter": "",
    "sender_equals": "",
    "subject_filter": "",
    "subject_equals": "",
    "attachment_name_contains": "",
    "attachment_name_equals": "",
    "auto_check_on_open": False,
    "check_on_refresh": True,
    "poll_interval_seconds": 60,
}

DEFAULT_SETTINGS = {
    "imap": DEFAULT_IMAP_BLOCK.copy(),
    "imap_approach": {
        **DEFAULT_IMAP_BLOCK,
        "subject_equals": "Отчёт слежения дислокация ТУ",
        "attachment_name_contains": ".xlsx",
    },
    "imap_departure": {
        **DEFAULT_IMAP_BLOCK,
        "subject_equals": "Отчёт слежения Дислокация ТУ грузоотправитель",
        "attachment_name_contains": ".xlsx",
    },
}

DEFAULT_LICENSE_SETTINGS = {
    "enabled": True,
    "require_license": True,
    "storage_dirname": "ASU_PODHOD",
    "license_filename": "license.lic",
    "request_extension": ".asureq",
    "public_key_file": "license_public_key.pem",
    "version_url": "",
    "revoked_url": "",
    "current_version": APP_VERSION,
    "allow_offline_cache": True,
    "check_revoked_on_startup": True,
    "check_updates_on_open": True,
    "activation_help_text": (
        "Сохраните файл запроса на активацию и отправьте его администратору. "
        "В ответ загрузите полученный файл лицензии (*.lic)."
    ),
}


def get_user_data_dir() -> Path:
    root = (
        os.environ.get("APPDATA")
        or os.environ.get("LOCALAPPDATA")
        or str(Path.home())
    )
    target = Path(root) / "ASU_PODHOD"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_user_data_subdir(name: str) -> Path:
    target = get_user_data_dir() / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_user_data_file(filename: str) -> Path:
    return get_user_data_dir() / filename


def get_station_directory_path() -> Path:
    return get_user_data_file(STATION_DIRECTORY_FILE)
