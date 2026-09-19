"""Coordinate deferred editor view-state capture outside the scroll hot path."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal


class EditorViewStateCoordinator(QObject):
    """Capture expensive editor viewport state only after scrolling settles."""

    state_captured = Signal(str, object)
    current_view_resolved = Signal(str, int, int)

    _DEFAULT_IDLE_MS = 90

    def __init__(
        self,
        current_editor_provider: Callable[[], object | None],
        parent=None,
        *,
        idle_ms: int = _DEFAULT_IDLE_MS,
    ) -> None:
        """Create one coordinator for the EditorPanel."""
        super().__init__(parent)
        self._current_editor_provider = current_editor_provider
        self._pending_editor: object | None = None
        self._pending_path: Path | None = None
        self._pending_resolve_current_view = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(int(idle_ms), 0))
        self._timer.timeout.connect(self.flush_pending)

    def request_capture(
        self,
        editor: object,
        path: str | Path,
        *,
        resolve_current_view: bool,
    ) -> None:
        """Remember the latest view activity without querying QTextDocument geometry."""
        self._pending_editor = editor
        self._pending_path = Path(path)
        self._pending_resolve_current_view = bool(resolve_current_view)
        self._timer.start()

    def flush_pending(self) -> None:
        """Capture the latest pending state after the view becomes idle."""
        editor = self._pending_editor
        path = self._pending_path
        resolve_current_view = self._pending_resolve_current_view
        self._clear_pending()
        if editor is None or path is None:
            return
        self.capture_now(
            editor,
            path,
            resolve_current_view=resolve_current_view,
        )

    def capture_now(
        self,
        editor: object,
        path: str | Path,
        *,
        resolve_current_view: bool,
    ) -> None:
        """Capture one editor state synchronously for tab switch/session boundaries."""
        try:
            state = dict(editor.view_state())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return

        path_value = str(Path(path))
        self.state_captured.emit(path_value, state)

        if not resolve_current_view:
            return
        if editor is not self._current_editor_provider():
            return

        try:
            line = int(state["visible_source_line"])
            column = int(state["visible_source_column"])
        except (KeyError, TypeError, ValueError):
            try:
                line, column = editor.first_visible_source_position()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                return

        self.current_view_resolved.emit(
            path_value,
            max(int(line), 1),
            max(int(column), 1),
        )

    def cancel_editor(self, editor: object) -> None:
        """Discard pending work for an editor that is being closed."""
        if self._pending_editor is not editor:
            return
        self._timer.stop()
        self._clear_pending()

    def _clear_pending(self) -> None:
        """Clear one pending capture request."""
        self._pending_editor = None
        self._pending_path = None
        self._pending_resolve_current_view = False
