from __future__ import annotations

from pathlib import Path
from typing import Optional


class OutlookMailError(RuntimeError):
    pass


class OutlookMailSender:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import win32com.client  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on Windows/pywin32
            raise OutlookMailError(
                "Не удалось подключиться к Outlook. Требуется установленный Outlook и пакет pywin32."
            ) from exc
        try:
            self._client = win32com.client.Dispatch("Outlook.Application")
            return self._client
        except Exception as exc:  # pragma: no cover
            raise OutlookMailError("Не удалось открыть Outlook.Application.") from exc

    def send_mail(
        self,
        *,
        to: str,
        cc: str = "",
        bcc: str = "",
        subject: str,
        body: str,
        attachment_path: Path,
    ) -> None:
        app = self._get_client()
        mail_item = app.CreateItem(0)
        mail_item.To = to or ""
        mail_item.CC = cc or ""
        mail_item.BCC = bcc or ""
        mail_item.Subject = subject or ""
        mail_item.Body = body or ""
        if attachment_path:
            file_path = str(Path(attachment_path).resolve())
            if not Path(file_path).exists():
                raise OutlookMailError(f"Вложение не найдено: {file_path}")
            mail_item.Attachments.Add(file_path)
        try:
            mail_item.Send()
        except Exception as exc:  # pragma: no cover
            raise OutlookMailError("Outlook не смог отправить письмо автоматически.") from exc
