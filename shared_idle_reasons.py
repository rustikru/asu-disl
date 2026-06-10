from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .config import get_user_data_subdir

_SHARED_DIRNAME = "shared_idle_reasons"
_SHARED_REASONS_FILE = "reasons.json"
_SHARED_COMMENTS_FILE = "comments.json"


def shared_reasons_path() -> Path:
    return get_user_data_subdir(_SHARED_DIRNAME) / _SHARED_REASONS_FILE


def shared_comments_path() -> Path:
    return get_user_data_subdir(_SHARED_DIRNAME) / _SHARED_COMMENTS_FILE


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


def _clean_reason_items(items: Iterable[object]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        folded = value.casefold()
        if not value or folded in seen:
            continue
        seen.add(folded)
        cleaned.append(value)
    return cleaned


def load_shared_reasons(*legacy_paths: Path) -> list[str]:
    path = shared_reasons_path()
    data = _load_json(path, None)
    if isinstance(data, dict):
        items = data.get("reasons", [])
        if isinstance(items, list):
            return _clean_reason_items(items)
    for legacy_path in legacy_paths:
        legacy = _load_json(legacy_path, None)
        if isinstance(legacy, dict):
            items = legacy.get("reasons", [])
            if isinstance(items, list):
                cleaned = _clean_reason_items(items)
                if cleaned:
                    save_shared_reasons(cleaned)
                    return cleaned
    return []


def save_shared_reasons(items: Iterable[object]) -> None:
    _save_json(shared_reasons_path(), {"reasons": _clean_reason_items(items)})


def _normalize_wagon_number(value: object) -> str:
    text = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return text or str(value or '').strip()


def _normalize_arrived_iso(value: object) -> str:
    return str(value or '').strip()


def _normalize_cycle_id(value: object) -> str:
    return str(value or '').strip()


def _normalize_effective_date(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    for parser in (lambda s: datetime.fromisoformat(s[:10]).date(), lambda s: datetime.strptime(s[:10], '%d.%m.%Y').date()):
        try:
            return parser(text).isoformat()
        except Exception:
            continue
    return ''


def _clean_comment_history(items: object) -> list[dict]:
    if not isinstance(items, list):
        return []
    cleaned: dict[str, dict] = {}
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        effective_date = _normalize_effective_date(raw_item.get('effective_date') or raw_item.get('date') or raw_item.get('updated_at'))
        if not effective_date:
            continue
        comment_text = str(raw_item.get('comment_text', '') or '').strip()
        updated_at = str(raw_item.get('updated_at', '') or '').strip()
        cleaned[effective_date] = {
            'effective_date': effective_date,
            'comment_text': comment_text,
            'updated_at': updated_at,
        }
    return [cleaned[key] for key in sorted(cleaned)]


def comment_storage_key(wagon_number: object, arrived_at_iso: object = '', cycle_id: object = '') -> str:
    wagon = _normalize_wagon_number(wagon_number)
    arrived = _normalize_arrived_iso(arrived_at_iso)
    cycle = _normalize_cycle_id(cycle_id)
    if not wagon:
        return ''
    if cycle:
        return f"{wagon}|cycle:{cycle}"
    return f"{wagon}|{arrived}" if arrived else wagon


def _clean_comment_mapping(payload: object) -> dict[str, dict]:
    comments = payload.get("comments", {}) if isinstance(payload, dict) else payload
    if not isinstance(comments, dict):
        return {}
    cleaned: dict[str, dict] = {}
    for raw_key, raw_value in comments.items():
        key = str(raw_key or '').strip()
        if not key or not isinstance(raw_value, dict):
            continue
        wagon_number = _normalize_wagon_number(raw_value.get('wagon_number') or key.split('|', 1)[0])
        cycle_id = _normalize_cycle_id(raw_value.get('cycle_id') or (key.split('|cycle:', 1)[1] if '|cycle:' in key else ''))
        arrived_tail = ''
        if '|cycle:' not in key and '|' in key:
            arrived_tail = key.split('|', 1)[1]
        arrived_at_iso = _normalize_arrived_iso(raw_value.get('arrived_at_iso') or arrived_tail)
        storage_key = comment_storage_key(wagon_number, arrived_at_iso, cycle_id) or key
        history = _clean_comment_history(raw_value.get('history'))
        cleaned[storage_key] = {
            'wagon_number': wagon_number,
            'comment_text': str(raw_value.get('comment_text', '') or '').strip(),
            'updated_at': str(raw_value.get('updated_at', '') or '').strip(),
            'arrived_at_iso': arrived_at_iso,
            'cycle_id': cycle_id,
            'history': history,
        }
        if history:
            latest = history[-1]
            cleaned[storage_key]['comment_text'] = str(latest.get('comment_text', '') or '').strip()
            cleaned[storage_key]['updated_at'] = str(latest.get('updated_at', '') or '').strip()
    return cleaned


def load_shared_comments(*legacy_paths: Path) -> dict[str, dict]:
    path = shared_comments_path()
    data = _load_json(path, None)
    cleaned = _clean_comment_mapping(data)
    if cleaned:
        return cleaned
    for legacy_path in legacy_paths:
        legacy = _load_json(legacy_path, None)
        cleaned = _clean_comment_mapping(legacy)
        if cleaned:
            save_shared_comments(cleaned)
            return cleaned
    return {}


def save_shared_comments(comments: dict[str, dict]) -> None:
    _save_json(shared_comments_path(), {"comments": _clean_comment_mapping(comments)})


def get_shared_comment(comments: dict[str, dict], wagon_number: object, arrived_at_iso: object = '', effective_date: object = '', cycle_id: object = '') -> tuple[str, str]:
    if not isinstance(comments, dict):
        return '', ''
    wagon = _normalize_wagon_number(wagon_number)
    arrived = _normalize_arrived_iso(arrived_at_iso)
    cycle = _normalize_cycle_id(cycle_id)
    if not wagon:
        return '', ''
    direct_key = comment_storage_key(wagon, arrived, cycle) if cycle else comment_storage_key(wagon, arrived)
    target_effective_date = _normalize_effective_date(effective_date)

    def _pick(item: dict) -> tuple[str, str]:
        history = _clean_comment_history(item.get('history'))
        if history:
            selected = None
            if target_effective_date:
                eligible = [entry for entry in history if entry.get('effective_date', '') <= target_effective_date]
                if eligible:
                    selected = eligible[-1]
            if selected is None:
                selected = history[-1]
            return str(selected.get('comment_text', '') or '').strip(), str(selected.get('updated_at', '') or '').strip()
        return str(item.get('comment_text', '') or '').strip(), str(item.get('updated_at', '') or '').strip()

    if direct_key and isinstance(comments.get(direct_key), dict):
        return _pick(comments.get(direct_key, {}))
    if cycle:
        for item in comments.values():
            if not isinstance(item, dict):
                continue
            if _normalize_wagon_number(item.get('wagon_number')) != wagon:
                continue
            if _normalize_cycle_id(item.get('cycle_id')) == cycle:
                return _pick(item)
    legacy_key = comment_storage_key(wagon, '')
    if legacy_key and isinstance(comments.get(legacy_key), dict):
        return _pick(comments.get(legacy_key, {}))
    for item in comments.values():
        if not isinstance(item, dict):
            continue
        if _normalize_wagon_number(item.get('wagon_number')) != wagon:
            continue
        saved_arrived = _normalize_arrived_iso(item.get('arrived_at_iso'))
        saved_cycle = _normalize_cycle_id(item.get('cycle_id'))
        if cycle and saved_cycle and saved_cycle != cycle:
            continue
        if arrived and saved_arrived and saved_arrived != arrived:
            continue
        return _pick(item)
    return '', ''



def get_shared_comment_history(comments: dict[str, dict], wagon_number: object, arrived_at_iso: object = '', cycle_id: object = '') -> list[dict]:
    if not isinstance(comments, dict):
        return []
    wagon = _normalize_wagon_number(wagon_number)
    arrived = _normalize_arrived_iso(arrived_at_iso)
    cycle = _normalize_cycle_id(cycle_id)
    if not wagon:
        return []
    direct_key = comment_storage_key(wagon, arrived, cycle) if cycle else comment_storage_key(wagon, arrived)
    if direct_key and isinstance(comments.get(direct_key), dict):
        return _clean_comment_history(comments.get(direct_key, {}).get('history'))
    if cycle:
        for item in comments.values():
            if not isinstance(item, dict):
                continue
            if _normalize_wagon_number(item.get('wagon_number')) != wagon:
                continue
            if _normalize_cycle_id(item.get('cycle_id')) == cycle:
                return _clean_comment_history(item.get('history'))
    legacy_key = comment_storage_key(wagon, '')
    if legacy_key and isinstance(comments.get(legacy_key), dict):
        return _clean_comment_history(comments.get(legacy_key, {}).get('history'))
    for item in comments.values():
        if not isinstance(item, dict):
            continue
        if _normalize_wagon_number(item.get('wagon_number')) != wagon:
            continue
        saved_arrived = _normalize_arrived_iso(item.get('arrived_at_iso'))
        saved_cycle = _normalize_cycle_id(item.get('cycle_id'))
        if cycle and saved_cycle and saved_cycle != cycle:
            continue
        if arrived and saved_arrived and saved_arrived != arrived:
            continue
        return _clean_comment_history(item.get('history'))
    return []

def set_shared_comment(comments: dict[str, dict], wagon_number: object, arrived_at_iso: object, comment_text: object, updated_at: object, effective_date: object = '', cycle_id: object = '') -> dict[str, dict]:
    payload = _clean_comment_mapping(comments)
    wagon = _normalize_wagon_number(wagon_number)
    arrived = _normalize_arrived_iso(arrived_at_iso)
    cycle = _normalize_cycle_id(cycle_id)
    if not wagon:
        return payload
    new_text = str(comment_text or '').strip()
    storage_key = comment_storage_key(wagon, arrived, cycle) if cycle else comment_storage_key(wagon, arrived)
    target_date = _normalize_effective_date(effective_date)
    existing_item = None
    for key, item in list(payload.items()):
        if not isinstance(item, dict):
            continue
        same_wagon = _normalize_wagon_number(item.get('wagon_number')) == wagon
        item_cycle = _normalize_cycle_id(item.get('cycle_id'))
        same_cycle = bool(cycle) and item_cycle == cycle
        same_arrived = (not cycle) and (_normalize_arrived_iso(item.get('arrived_at_iso')) == arrived or key == wagon)
        if same_wagon and (same_cycle or same_arrived):
            existing_item = item
            if key != storage_key:
                payload.pop(key, None)
            break
    if target_date:
        base_item = dict(existing_item or {})
        history = _clean_comment_history(base_item.get('history'))
        history = [entry for entry in history if entry.get('effective_date') != target_date]
        if new_text:
            history.append({
                'effective_date': target_date,
                'comment_text': new_text,
                'updated_at': str(updated_at or '').strip(),
            })
            history = _clean_comment_history(history)
        latest = history[-1] if history else None
        if latest or new_text:
            payload[storage_key] = {
                'wagon_number': wagon,
                'comment_text': str((latest or {}).get('comment_text', '') or '').strip(),
                'updated_at': str((latest or {}).get('updated_at', '') or '').strip(),
                'arrived_at_iso': arrived,
                'cycle_id': cycle,
                'history': history,
            }
        return payload
    keys_to_remove = [
        key for key, item in payload.items()
        if isinstance(item, dict)
        and _normalize_wagon_number(item.get('wagon_number')) == wagon
        and ((cycle and _normalize_cycle_id(item.get('cycle_id')) == cycle) or ((not cycle) and (_normalize_arrived_iso(item.get('arrived_at_iso')) == arrived or key == wagon)))
    ]
    for key in keys_to_remove:
        payload.pop(key, None)
    if new_text:
        payload[storage_key] = {
            'wagon_number': wagon,
            'comment_text': new_text,
            'updated_at': str(updated_at or '').strip(),
            'arrived_at_iso': arrived,
            'cycle_id': cycle,
            'history': _clean_comment_history((existing_item or {}).get('history')),
        }
    return payload


def prune_shared_comments_to_keys(comments: dict[str, dict], allowed_keys: Iterable[str]) -> dict[str, dict]:
    payload = _clean_comment_mapping(comments)
    allowed = {str(key or '').strip() for key in allowed_keys if str(key or '').strip()}
    return {key: value for key, value in payload.items() if key in allowed}
