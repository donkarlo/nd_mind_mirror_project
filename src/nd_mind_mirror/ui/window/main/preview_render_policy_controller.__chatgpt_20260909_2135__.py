"""Coordinate preview render policy without replacing renderer methods at runtime."""

from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class PreviewRenderPolicyController(QObject):
    """Handle immediate first-open rendering and fast structural-input validation."""

    _SMALL_SOURCE_CHARS = 60_000
    _LATEX_SUFFIXES = {".tex", ".tikz"}

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
        self._validate_structural_inputs(source, resolved)

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
        resolved = self._resolve_latex_path(str(path))
        if resolved is None:
            self._last_missing_input = ""
            return
        try:
            source = editor.toPlainText()
        except AttributeError:
            return
        self._validate_structural_inputs(str(source), resolved)

    def _validate_structural_inputs(
        self,
        source: str,
        source_path: Path,
    ) -> None:
        """Validate through the renderer's canonical workspace-aware resolver."""
        missing = self._renderer.first_missing_latex_input(
            source=source,
            source_path=source_path,
        )
        if missing is None:
            self._last_missing_input = ""
            return
        if missing == self._last_missing_input:
            return
        self._last_missing_input = missing
        self._renderer.failed.emit(f"Missing LaTeX input: {missing}")

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
