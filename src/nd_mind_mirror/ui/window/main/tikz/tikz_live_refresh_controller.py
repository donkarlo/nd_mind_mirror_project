"""Bounded live-refresh scheduling for external TikZ edits."""

from __future__ import annotations

from pathlib import Path
import math
import time

from PySide6.QtCore import QObject, QTimer, Signal


class TikZLiveRefreshController(QObject):
    """Throttle live projections while delaying full PDF compilation until idle."""

    live_refresh_requested = Signal(object)
    pdf_refresh_requested = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        live_interval_ms: int = 80,
        pdf_idle_delay_ms: int = 650,
    ) -> None:
        super().__init__(parent)
        self._live_interval_ms = max(int(live_interval_ms), 1)
        self._pending_paths: set[Path] = set()
        self._last_live_refresh_at = -float("inf")

        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.timeout.connect(self._flush_live)

        self._pdf_timer = QTimer(self)
        self._pdf_timer.setSingleShot(True)
        self._pdf_timer.setInterval(max(int(pdf_idle_delay_ms), 1))
        self._pdf_timer.timeout.connect(self.pdf_refresh_requested.emit)

    def submit(self, path: str | Path) -> None:
        """Queue a source path for the next live frame and restart idle PDF delay."""
        self._pending_paths.add(Path(path).expanduser().resolve(strict=False))
        self._schedule_live()
        self._pdf_timer.start()

    def stop(self) -> None:
        self._live_timer.stop()
        self._pdf_timer.stop()
        self._pending_paths.clear()

    def _schedule_live(self) -> None:
        if self._live_timer.isActive():
            return

        elapsed_ms = (
            time.monotonic() - self._last_live_refresh_at
        ) * 1000.0
        if elapsed_ms >= self._live_interval_ms:
            self._live_timer.start(0)
            return

        remaining_ms = max(
            int(math.ceil(self._live_interval_ms - elapsed_ms)),
            1,
        )
        self._live_timer.start(remaining_ms)

    def _flush_live(self) -> None:
        if not self._pending_paths:
            return

        paths = tuple(sorted(self._pending_paths, key=str))
        self._pending_paths.clear()
        self._last_live_refresh_at = time.monotonic()
        self.live_refresh_requested.emit(paths)
