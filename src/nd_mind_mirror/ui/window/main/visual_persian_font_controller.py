"""Apply a configurable Persian/Arabic font to LaTeX Visual editor text efficiently."""

from __future__ import annotations

from pathlib import Path
import weakref

import yaml
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class PersianVisualFontHighlighter(QSyntaxHighlighter):
    """Overlay one font family on Arabic-script Visual runs without per-character QTextCursor work."""

    def __init__(self, document, font_family: str) -> None:
        """Attach to a Visual document and store the Arabic-script font family."""
        super().__init__(document)
        self._font_family = str(font_family).strip()

    def set_font_family(self, font_family: str) -> None:
        """Update the overlay font family and rehighlight the bounded Visual document."""
        value = str(font_family).strip()
        if value == self._font_family:
            return
        self._font_family = value
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        """Apply the configured family to contiguous Arabic-script runs in linear time."""
        if not self._font_family or not text:
            return

        run_start: int | None = None
        for offset, char in enumerate(text):
            if self._is_arabic_script_character(char):
                if run_start is None:
                    run_start = offset
                continue
            if run_start is not None:
                self._set_font_run(run_start, offset - run_start)
                run_start = None

        if run_start is not None:
            self._set_font_run(run_start, len(text) - run_start)

    def _set_font_run(self, start: int, length: int) -> None:
        """Set only the font-family overlay for one Visual character run."""
        if length <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontFamily(self._font_family)
        self.setFormat(start, length, fmt)

    @staticmethod
    def _is_arabic_script_character(char: str) -> bool:
        """Return whether a character belongs to Arabic-script ranges used by Persian."""
        if not char:
            return False
        code = ord(char)
        return (
            0x0600 <= code <= 0x08FF
            or 0xFB50 <= code <= 0xFDFF
            or 0xFE70 <= code <= 0xFEFF
            or code in {0x200C, 0x200D}
        )


class VisualPersianFontController:
    """Attach fast script-sensitive font overlays to LaTeX Visual editors and reload their setting."""

    DEFAULT_FONT_FAMILY = "Noto Naskh Arabic"

    def __init__(self, editor_panel, app_settings, parent=None) -> None:
        """Bind current/future Visual editors and apply the persisted Persian font preference."""
        self._editor_panel = editor_panel
        self._app_settings = app_settings
        self._parent = parent
        self._font_family = self.DEFAULT_FONT_FAMILY
        self._highlighters: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

        editor_panel.current_document_changed.connect(self._on_editor_context_changed)
        editor_panel.current_view_changed.connect(self._on_editor_context_changed)
        self.reload()

    def reload(self) -> None:
        """Reload the Visual Persian font from settings.yaml and refresh all bound overlays."""
        self._font_family = self._read_visual_persian_font_family(
            self._app_settings.settings_path
        )
        self._bind_current_editor()
        for highlighter in list(self._highlighters.values()):
            highlighter.set_font_family(self._font_family)

    def _on_editor_context_changed(self, *_args) -> None:
        """Attach the overlay when the active document or edit view changes."""
        self._bind_current_editor()

    def _bind_current_editor(self) -> None:
        """Create exactly one Persian font overlay for the active LaTeX Visual editor."""
        editor = self._editor_panel.current_editor()
        if not isinstance(editor, LatexEditor):
            return
        visual_editor = editor._visual_editor
        if visual_editor in self._highlighters:
            return
        self._highlighters[visual_editor] = PersianVisualFontHighlighter(
            visual_editor.document(),
            self._font_family,
        )

    @classmethod
    def _read_visual_persian_font_family(cls, settings_path: str | Path) -> str:
        """Read the Visual Persian font preference directly from the merged settings file."""
        try:
            data = yaml.safe_load(Path(settings_path).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return cls.DEFAULT_FONT_FAMILY
        editor = data.get("editor", {}) if isinstance(data, dict) else {}
        if not isinstance(editor, dict):
            return cls.DEFAULT_FONT_FAMILY
        value = str(editor.get("visual_persian_font_family", "")).strip()
        return value or cls.DEFAULT_FONT_FAMILY

    @staticmethod
    def _is_arabic_script_character(char: str) -> bool:
        """Expose Arabic-script detection for settings/controller regression tests."""
        return PersianVisualFontHighlighter._is_arabic_script_character(char)
