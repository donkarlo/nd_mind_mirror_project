"""Coalesce rapid generated-PDF handoffs before they reach Qt Quick PDF."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal


class PdfHandoffCoalescer(QObject):
    """Keep Qt Quick PdfDocument reloads serialized and latest-generation-first."""

    handoff_requested = Signal(object, bool)

    def __init__(
        self,
        minimum_interval_ms: int = 180,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._minimum_interval_ms = max(int(minimum_interval_ms), 80)
        self._last_handoff_at = 0.0
        self._pending_path: Path | None = None
        self._pending_reset_position = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(
            self._emit_pending
        )

    @property
    def has_pending(self) -> bool:
        return self._pending_path is not None

    def request(
        self,
        path: str | Path,
        reset_position: bool,
    ) -> None:
        """Dispatch immediately when safe; otherwise retain only the newest PDF."""
        pdf_path = Path(path).expanduser().resolve()
        now = time.monotonic()
        elapsed_ms = (
            (now - self._last_handoff_at) * 1000.0
            if self._last_handoff_at > 0.0
            else float("inf")
        )

        if (
            elapsed_ms >= self._minimum_interval_ms
            and not self._timer.isActive()
            and self._pending_path is None
        ):
            self._last_handoff_at = now
            self.handoff_requested.emit(
                pdf_path,
                bool(reset_position),
            )
            return

        self._pending_path = pdf_path
        self._pending_reset_position = bool(reset_position)

        remaining_ms = max(
            int(round(self._minimum_interval_ms - elapsed_ms)),
            1,
        )
        self._timer.start(remaining_ms)

    def cancel_pending(self) -> None:
        """Discard stale successful generations after a newer compile failure."""
        self._timer.stop()
        self._pending_path = None
        self._pending_reset_position = False

    def _emit_pending(self) -> None:
        path = self._pending_path
        if path is None:
            return

        reset_position = self._pending_reset_position
        self._pending_path = None
        self._pending_reset_position = False
        self._last_handoff_at = time.monotonic()

        self.handoff_requested.emit(
            path,
            reset_position,
        )
