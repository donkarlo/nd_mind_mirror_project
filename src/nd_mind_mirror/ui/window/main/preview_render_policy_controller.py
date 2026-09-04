"""Coordinate preview render policy without replacing renderer methods at runtime."""

from pathlib import Path
import re

from PySide6.QtCore import QObject, QTimer


class PreviewRenderPolicyController(QObject):
    """Handle immediate first-open rendering and fast absolute-input validation."""

    _SMALL_SOURCE_CHARS = 60_000
    _LATEX_SUFFIXES = {".tex", ".tikz"}
    _ABSOLUTE_INPUT_PATTERN = re.compile(
        r"\\(?:input|include)\s*\{(?P<path>/[^{}]+)\}"
    )

    def __init__(self, editor_panel, renderer, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._renderer = renderer
        self._last_render_path: Path | None = None
        self._last_missing_input = ""

        self._editor_panel.current_document_changed.connect(
            self._on_current_document_changed
        )
        self._editor_panel.current_content_changed.connect(
            lambda *_args: self._validate_current_document()
        )
        QTimer.singleShot(0, self._initialize_current_document)

    def _initialize_current_document(self) -> None:
        path = self._editor_panel.current_path()
        editor = self._editor_panel.current_editor()
        if path is None or editor is None:
            return
        try:
            content = editor.toPlainText()
        except AttributeError:
            return
        self._handle_document(str(path), str(content))

    def _on_current_document_changed(self, path: str, content: str) -> None:
        self._handle_document(path, content)

    def _handle_document(self, path: str, content: str) -> None:
        resolved = self._resolve_latex_path(path)
        if resolved is None:
            return

        source = str(content or "")
        self._validate_absolute_inputs(source)

        first_small_open = (
            len(source) < self._SMALL_SOURCE_CHARS
            and resolved != self._last_render_path
        )
        self._last_render_path = resolved
        if not first_small_open:
            return

        self._renderer.render(
            source,
            source_path=resolved,
            immediate=True,
        )

    def _validate_current_document(self) -> None:
        path = self._editor_panel.current_path()
        editor = self._editor_panel.current_editor()
        if path is None or editor is None:
            self._last_missing_input = ""
            return
        if self._resolve_latex_path(str(path)) is None:
            self._last_missing_input = ""
            return
        try:
            source = editor.toPlainText()
        except AttributeError:
            return
        self._validate_absolute_inputs(str(source))

    def _validate_absolute_inputs(self, source: str) -> None:
        missing = self._first_missing_absolute_input(source)
        if missing is None:
            self._last_missing_input = ""
            return
        if missing == self._last_missing_input:
            return
        self._last_missing_input = missing
        self._renderer.failed.emit(f"Missing LaTeX input: {missing}")

    @classmethod
    def _first_missing_absolute_input(cls, source: str) -> str | None:
        for match in cls._ABSOLUTE_INPUT_PATTERN.finditer(source):
            raw_path = match.group("path").strip()
            candidate = Path(raw_path).expanduser()
            options = [candidate]
            if not candidate.suffix:
                options.append(candidate.with_suffix(".tex"))
            if not any(option.is_file() for option in options):
                return raw_path
        return None

    @classmethod
    def _resolve_latex_path(cls, path: str) -> Path | None:
        if not path:
            return None
        try:
            resolved = Path(path).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return None
        if resolved.suffix.lower() not in cls._LATEX_SUFFIXES:
            return None
        return resolved
