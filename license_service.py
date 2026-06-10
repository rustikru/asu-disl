from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
import socket
import urllib.error
import urllib.request
import uuid
from datetime import timezone
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .config import DEFAULT_LICENSE_SETTINGS, LICENSE_SETTINGS_FILE, get_user_data_file

try:
    from cryptography.hazmat.primitives import serialization
except Exception:  # pragma: no cover
    serialization = None


@dataclass
class LicenseState:
    active: bool
    reason: str
    device_code: str
    device_name: str
    os_user: str
    storage_dir: str
    local_license_path: str = ""
    license_payload: Optional[dict[str, Any]] = None


def load_license_settings(base_dir: Path) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_LICENSE_SETTINGS))
    path = get_user_data_file(LICENSE_SETTINGS_FILE)
    legacy_path = base_dir / LICENSE_SETTINGS_FILE
    if not path.exists() and legacy_path.exists():
        try:
            import shutil
            shutil.copy2(legacy_path, path)
        except Exception:
            pass
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged.update(data)
        except Exception:
            pass
    return merged


def get_storage_dir(settings: dict[str, Any]) -> Path:
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    target = Path(root) / str(settings.get("storage_dirname") or "ASU_PODHOD")
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_license_file_path(settings: dict[str, Any], base_dir: Optional[Path] = None) -> Path:
    path = get_storage_dir(settings) / str(settings.get("license_filename") or "license.lic")
    if base_dir is not None and not path.exists():
        legacy_path = base_dir / str(settings.get("license_filename") or "license.lic")
        if legacy_path.exists():
            try:
                import shutil
                shutil.copy2(legacy_path, path)
            except Exception:
                pass
    return path


def get_cache_file_path(settings: dict[str, Any], name: str) -> Path:
    return get_storage_dir(settings) / name


def _get_windows_machine_guid() -> str:
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0] or "")
    except Exception:
        return ""


def get_device_name() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "UNKNOWN-PC"


def get_os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME", "")


def get_device_code() -> str:
    computer = get_device_name().upper().strip()
    os_user = get_os_user().upper().strip()
    machine_guid = _get_windows_machine_guid().upper().strip()
    mac = f"{uuid.getnode():012X}"
    raw = "|".join([computer, os_user, machine_guid, mac])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:16]
    return "ASU-" + "-".join([digest[i:i + 4] for i in range(0, len(digest), 4)])

def build_activation_request_payload(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "asu_podhod_activation_request",
        "schema_version": 1,
        "request_created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "app_name": "АСУ Подход",
        "app_version": str(settings.get("current_version") or ""),
        "device_code": get_device_code(),
        "device_name": get_device_name(),
        "os_user": get_os_user(),
        "platform": platform.platform(),
    }


def build_activation_request_filename(payload: dict[str, Any], settings: dict[str, Any]) -> str:
    device_name = str(payload.get("device_name") or "pc").strip().replace(" ", "_")
    os_user = str(payload.get("os_user") or "user").strip().replace(" ", "_")
    extension = str(settings.get("request_extension") or ".asureq")
    if not extension.startswith('.'):
        extension = '.' + extension
    return f"activation_request_{os_user}_{device_name}{extension}"


def parse_activation_request_bytes(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Не удалось прочитать файл запроса: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Файл запроса должен содержать JSON-объект.")
    if str(payload.get("format") or "") != "asu_podhod_activation_request":
        raise ValueError("Некорректный формат файла запроса.")
    device_code = str(payload.get("device_code") or "").strip()
    if not device_code:
        raise ValueError("В файле запроса отсутствует код устройства.")
    return payload


def _canonical_payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_public_key(base_dir: Path, settings: dict[str, Any]):
    if serialization is None:
        raise RuntimeError("Не установлен пакет 'cryptography'. Выполните: py -m pip install cryptography")
    public_key_path = base_dir / str(settings.get("public_key_file") or "license_public_key.pem")
    if not public_key_path.exists():
        raise FileNotFoundError(f"Не найден публичный ключ: {public_key_path}")
    data = public_key_path.read_bytes()
    return serialization.load_pem_public_key(data)


def _parse_license_content(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError(f"Не удалось прочитать файл лицензии: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Файл лицензии должен содержать JSON-объект.")
    if "payload" not in payload or "signature" not in payload:
        raise ValueError("Некорректный формат лицензии: ожидаются поля payload и signature.")
    if not isinstance(payload["payload"], dict) or not isinstance(payload["signature"], str):
        raise ValueError("Некорректный формат payload/signature.")
    return payload


def _verify_signature(base_dir: Path, settings: dict[str, Any], license_object: dict[str, Any]) -> dict[str, Any]:
    public_key = _load_public_key(base_dir, settings)
    payload = license_object["payload"]
    signature_b64 = license_object["signature"]
    try:
        signature = base64.b64decode(signature_b64.encode("ascii"))
    except Exception as exc:
        raise ValueError("Не удалось декодировать подпись лицензии.") from exc
    try:
        public_key.verify(signature, _canonical_payload_bytes(payload))
    except Exception as exc:
        raise ValueError("Подпись лицензии недействительна.") from exc
    return payload


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _version_tuple(value: Any) -> tuple[int, ...]:
    text = str(value or "").strip()
    if not text:
        return tuple()
    cleaned = []
    for part in text.replace("-", ".").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        cleaned.append(int(digits or 0))
    return tuple(cleaned)


def _is_version_allowed(payload: dict[str, Any], current_version: str) -> bool:
    current = _version_tuple(current_version)
    min_v = payload.get("min_version")
    max_v = payload.get("max_version")
    if min_v and current and current < _version_tuple(min_v):
        return False
    if max_v and current and current > _version_tuple(max_v):
        return False
    if payload.get("max_major_version"):
        try:
            max_major = int(payload["max_major_version"])
            if current and current[0] > max_major:
                return False
        except Exception:
            pass
    return True


def validate_license_bytes(raw: bytes, base_dir: Path, settings: dict[str, Any], device_code: Optional[str] = None) -> dict[str, Any]:
    license_object = _parse_license_content(raw)
    payload = _verify_signature(base_dir, settings, license_object)

    current_device_code = device_code or get_device_code()
    if str(payload.get("device_code") or "").strip() != current_device_code:
        raise ValueError("Эта лицензия выпущена для другого компьютера.")

    expires_at = _parse_date(payload.get("expires_at"))
    if expires_at and date.today() > expires_at:
        raise ValueError("Срок действия лицензии истёк.")

    current_version = str(settings.get("current_version") or "").strip()
    if current_version and not _is_version_allowed(payload, current_version):
        raise ValueError("Лицензия не подходит для текущей версии приложения.")

    return payload


def install_license_file(file_bytes: bytes, base_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    payload = validate_license_bytes(file_bytes, base_dir, settings)
    license_path = get_license_file_path(settings, base_dir)
    license_path.write_bytes(file_bytes)
    return payload


def remove_local_license(settings: dict[str, Any]) -> None:
    path = get_license_file_path(settings)
    if path.exists():
        path.unlink()


def _load_cached_json(cache_path: Path) -> Optional[dict[str, Any]]:
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _fetch_json_url(url: str, timeout: int = 8) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8"))


def fetch_remote_json(url: str, cache_path: Path, allow_cache: bool = True) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if not url:
        return None, None
    try:
        payload = _fetch_json_url(url)
        cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload, None
    except Exception as exc:
        if allow_cache:
            cached = _load_cached_json(cache_path)
            if cached is not None:
                return cached, f"облако недоступно, использован локальный кэш: {exc}"
        return None, str(exc)


def check_revoked(payload: Optional[dict[str, Any]], settings: dict[str, Any]) -> tuple[bool, Optional[str]]:
    if not payload or not settings.get("check_revoked_on_startup", True):
        return False, None
    revoked_url = str(settings.get("revoked_url") or "").strip()
    cache_path = get_cache_file_path(settings, "revoked_cache.json")
    revoked_data, error = fetch_remote_json(revoked_url, cache_path, allow_cache=bool(settings.get("allow_offline_cache", True)))
    if not revoked_data:
        return False, error
    revoked_list = revoked_data.get("revoked", [])
    if isinstance(revoked_list, list) and str(payload.get("license_id") or "") in {str(x) for x in revoked_list}:
        return True, None
    return False, error


def get_license_state(base_dir: Path, settings: dict[str, Any]) -> LicenseState:
    device_code = get_device_code()
    device_name = get_device_name()
    os_user = get_os_user()
    storage_dir = str(get_storage_dir(settings))
    license_path = get_license_file_path(settings, base_dir)

    if not settings.get("enabled", True) or not settings.get("require_license", True):
        return LicenseState(
            active=True,
            reason="Проверка лицензии отключена в настройках.",
            device_code=device_code,
            device_name=device_name,
            os_user=os_user,
            storage_dir=storage_dir,
            local_license_path=str(license_path) if license_path.exists() else "",
        )

    if not license_path.exists():
        return LicenseState(
            active=False,
            reason="Локальный файл лицензии не найден.",
            device_code=device_code,
            device_name=device_name,
            os_user=os_user,
            storage_dir=storage_dir,
            local_license_path=str(license_path),
        )

    try:
        raw = license_path.read_bytes()
        payload = validate_license_bytes(raw, base_dir, settings, device_code=device_code)
        is_revoked, revoke_error = check_revoked(payload, settings)
        if is_revoked:
            return LicenseState(
                active=False,
                reason="Эта лицензия была отозвана.",
                device_code=device_code,
                device_name=device_name,
                os_user=os_user,
                storage_dir=storage_dir,
                local_license_path=str(license_path),
                license_payload=payload,
            )
        reason = "Лицензия подтверждена."
        if revoke_error:
            reason = f"Лицензия подтверждена, но не удалось проверить отзыв: {revoke_error}"
        return LicenseState(
            active=True,
            reason=reason,
            device_code=device_code,
            device_name=device_name,
            os_user=os_user,
            storage_dir=storage_dir,
            local_license_path=str(license_path),
            license_payload=payload,
        )
    except Exception as exc:
        return LicenseState(
            active=False,
            reason=str(exc),
            device_code=device_code,
            device_name=device_name,
            os_user=os_user,
            storage_dir=storage_dir,
            local_license_path=str(license_path),
        )


def get_update_info(settings: dict[str, Any]) -> dict[str, Any]:
    info: dict[str, Any] = {
        "checked": False,
        "has_update": False,
        "latest_version": str(settings.get("current_version") or ""),
        "installer_url": "",
        "notes": [],
        "source_error": None,
    }
    if not settings.get("check_updates_on_open", True):
        return info

    version_url = str(settings.get("version_url") or "").strip()
    if not version_url:
        return info

    cache_path = get_cache_file_path(settings, "version_cache.json")
    payload, error = fetch_remote_json(version_url, cache_path, allow_cache=bool(settings.get("allow_offline_cache", True)))
    info["checked"] = True
    info["source_error"] = error
    if not payload:
        return info

    current_version = str(settings.get("current_version") or "").strip()
    latest_version = str(payload.get("latest_version") or current_version)
    info["latest_version"] = latest_version
    info["installer_url"] = str(payload.get("installer_url") or "")
    notes = payload.get("notes", [])
    if isinstance(notes, str):
        notes = [line.strip() for line in notes.splitlines() if line.strip()]
    if not isinstance(notes, list):
        notes = []
    info["notes"] = notes
    if _version_tuple(latest_version) > _version_tuple(current_version):
        info["has_update"] = True
    return info
