"""Map ordinary PDF preview clicks back to the active LaTeX Source or Visual location."""

from __future__ import annotations

from pathlib import Path
import re
import shutil

from PySide6.QtCore import QEvent, QObject, QProcess, QTimer, Qt


class PreviewReverseSyncController(QObject):
    """Observe preview clicks, run reverse SyncTeX, and navigate the active editor mode."""

    _MAX_CLICK_DRAG_PX = 7.0

    def __init__(self, main_window, parent=None) -> None:
        """Attach passive click observation to the existing selectable PDF view."""
        super().__init__(parent or main_window)
        self._window = main_window
        self._renderer = main_window._renderer
        self._panel = main_window._editor_panel
        self._pdf_view = main_window._preview_panel.preview._pdf_view
        self._press_position = None
        self._mapping_token = 0
        self._mapping_attempts = 0

        self._process = QProcess(self)
        self._process.finished.connect(self._on_synctex_finished)
        self._pdf_view.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Observe short left-clicks without consuming PDF text-selection events."""
        if watched is not self._pdf_view:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_position = event.position()
            else:
                self._press_position = None

        elif event.type() == QEvent.Type.MouseButtonRelease:
            if (
                event.button() == Qt.MouseButton.LeftButton
                and self._press_position is not None
            ):
                release = event.position()
                delta = release - self._press_position
                self._press_position = None
                if delta.manhattanLength() <= self._MAX_CLICK_DRAG_PX:
                    self._request_pdf_mapping(float(release.x()), float(release.y()))

        return super().eventFilter(watched, event)

    def _request_pdf_mapping(self, x: float, y: float) -> None:
        """Ask QML to convert viewport coordinates into a PDF page point."""
        root = self._pdf_view.rootObject()
        if root is None:
            return
        self._mapping_token += 1
        self._mapping_attempts = 0
        root.setProperty("reverseClickX", x)
        root.setProperty("reverseClickY", y)
        root.setProperty("reverseClickToken", self._mapping_token)
        QTimer.singleShot(0, self._consume_pdf_mapping)

    def _consume_pdf_mapping(self) -> None:
        """Read the QML mapping result after the current Qt Quick event pass."""
        root = self._pdf_view.rootObject()
        if root is None:
            return
        try:
            result_token = int(root.property("reverseClickResultToken"))
        except (TypeError, ValueError):
            result_token = -1

        if result_token != self._mapping_token:
            self._mapping_attempts += 1
            if self._mapping_attempts <= 4:
                QTimer.singleShot(20, self._consume_pdf_mapping)
            return

        try:
            page = int(root.property("reverseClickPage"))
            x = float(root.property("reverseClickPdfX"))
            y = float(root.property("reverseClickPdfY"))
        except (TypeError, ValueError):
            return
        if page < 0:
            return
        self._start_synctex(page, x, y)

    def _start_synctex(self, page: int, x: float, y: float) -> None:
        """Run `synctex edit` against the renderer's real preview PDF."""
        executable = shutil.which("synctex")
        pdf_path = Path(getattr(self._renderer, "_pdf_path", ""))
        if executable is None or not pdf_path.is_file():
            return

        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(150)

        self._process.setProgram(executable)
        self._process.setArguments(
            [
                "edit",
                "-o",
                f"{max(page + 1, 1)}:{x:.3f}:{y:.3f}:{pdf_path}",
            ]
        )
        self._process.setWorkingDirectory(str(pdf_path.parent))
        self._process.start()

    def _on_synctex_finished(self, exit_code: int, exit_status) -> None:
        """Parse reverse SyncTeX output and navigate the currently visible editor mode."""
        del exit_status
        if exit_code != 0:
            return
        output = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        line_match = re.search(r"(?m)^Line:(\d+)", output)
        column_match = re.search(r"(?m)^Column:(\d+)", output)
        if line_match is None:
            return

        preview_line = max(int(line_match.group(1)), 1)
        preview_column = (
            max(int(column_match.group(1)), 1)
            if column_match is not None
            else 1
        )
        source_line = self._source_line_for_preview_line(preview_line)
        if source_line is None:
            return

        source_path = getattr(self._renderer, "_cache_source_path", None)
        if source_path is None:
            return
        source_path = Path(source_path).expanduser().resolve()
        if not source_path.is_file():
            return

        self._window._open_path(str(source_path), select=True, reveal_in_navigator=True)
        QTimer.singleShot(
            0,
            lambda line=source_line, column=preview_column: self._navigate(line, column),
        )

    def _navigate(self, line: int, column: int) -> None:
        """Move Source or Visual according to whichever mode is currently active."""
        editor = self._panel.current_editor()
        if editor is None:
            return
        if hasattr(editor, "go_to_source_location"):
            editor.go_to_source_location(line, column, align_top=False)
        elif hasattr(editor, "go_to_line"):
            editor.go_to_line(line, align_top=False)

    def _source_line_for_preview_line(self, preview_line: int) -> int | None:
        """Invert the renderer's prepared-source mapping using line context and position."""
        source_text = str(getattr(self._renderer, "_current_source_text", "") or "")
        prepared_text = str(getattr(self._renderer, "_current_prepared_text", "") or "")
        source_lines = source_text.splitlines()
        prepared_lines = prepared_text.splitlines()
        if not source_lines or not prepared_lines:
            return None

        prepared_index = max(0, min(int(preview_line) - 1, len(prepared_lines) - 1))
        target = prepared_lines[prepared_index]

        candidates: list[int] = []
        if target.strip():
            candidates = [
                index for index, value in enumerate(source_lines) if value == target
            ]

        best_index: int | None = None
        best_rank: tuple[int, float, int] | None = None
        for source_index in candidates:
            context_score = 0
            for delta in (-4, -3, -2, -1, 1, 2, 3, 4):
                prepared_neighbor = prepared_index + delta
                source_neighbor = source_index + delta
                if (
                    0 <= prepared_neighbor < len(prepared_lines)
                    and 0 <= source_neighbor < len(source_lines)
                    and prepared_lines[prepared_neighbor] == source_lines[source_neighbor]
                ):
                    context_score += 1
            prepared_ratio = prepared_index / max(len(prepared_lines) - 1, 1)
            source_ratio = source_index / max(len(source_lines) - 1, 1)
            rank = (context_score, -abs(prepared_ratio - source_ratio), -source_index)
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_index = source_index

        if best_index is not None:
            return best_index + 1

        # Generated wrappers and recursively expanded inputs can remove exact
        # line identity. A ratio fallback still lands near the clicked region,
        # and the next normal click/cursor movement refines the mapping.
        ratio = prepared_index / max(len(prepared_lines) - 1, 1)
        return max(
            1,
            min(
                int(round(ratio * (len(source_lines) - 1))) + 1,
                len(source_lines),
            ),
        )
