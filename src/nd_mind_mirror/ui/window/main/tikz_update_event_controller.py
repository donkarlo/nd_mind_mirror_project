"""Low-latency desktop notification for canonical TikZ saves from the iPad."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal


class TikZUpdateEventController(QObject):
    """Observe canonical TikZ events even when the bridge runs externally."""

    updated = Signal(str)
    _ACTIVE_POLL_MS = 45
    _IDLE_POLL_MS = 60
    _COALESCE_MS = 55

    def __init__(self, workspace_root: str | Path, parent=None) -> None:
        super().__init__(parent)
        self._event_path = (
            Path(workspace_root).expanduser().resolve()
            / ".nd_mind_mirror"
            / "tikz_update_event.json"
        )
        self._signature: tuple[int, int] | None = self._file_signature()
        self._pending_path = ""

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._IDLE_POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(self._COALESCE_MS)
        self._emit_timer.timeout.connect(self._emit_pending)

    def _poll(self) -> None:
        # A healthy external bridge need not be owned/adopted by this window.
        # Always observe the tiny event file; a filesystem stat is inexpensive.
        self._set_poll_interval(self._ACTIVE_POLL_MS)
        signature = self._file_signature()
        if signature is None or signature == self._signature:
            return
        self._signature = signature
        try:
            payload = json.loads(self._event_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return
        path = str(payload.get("path", "")).strip()
        if not path:
            return
        self._pending_path = path
        self._emit_timer.start()

    def _set_poll_interval(self, interval_ms: int) -> None:
        interval = max(int(interval_ms), 1)
        if self._poll_timer.interval() != interval:
            self._poll_timer.setInterval(interval)

    def _emit_pending(self) -> None:
        path = self._pending_path
        self._pending_path = ""
        if path:
            self.updated.emit(path)

    def _file_signature(self) -> tuple[int, int] | None:
        try:
            stat = self._event_path.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_size)
