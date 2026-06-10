from __future__ import annotations

import socket

from flask import current_app, render_template_string

from .config import APP_TITLE
from .templates import BASE_HTML

def render_page(body: str, **context) -> str:
    body_html = render_template_string(body, **context)
    ui_preferences = {}
    try:
        ui_preferences = dict(current_app.config.get("UI_PREFERENCES") or {})
    except Exception:
        ui_preferences = {}
    page_context = dict(context)
    page_context.setdefault("title", context.get("title", APP_TITLE))
    page_context["body"] = body_html
    page_context.setdefault("ui_preferences", ui_preferences)
    return render_template_string(BASE_HTML, **page_context)

def best_lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"
