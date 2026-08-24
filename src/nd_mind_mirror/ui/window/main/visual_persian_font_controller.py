"""Apply a configurable Persian/Arabic font to LaTeX Visual editor text efficiently."""

from __future__ import annotations

from pathlib import Path
import unicodedata
import weakref

import yaml
from PySide6.QtGui import QFontDatabase, QSyntaxHighlighter, QTextCharFormat

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class PersianVisualFontHighlighter(QSyntaxHighlighter):
    """Overlay one shaping-capable font family on complete Arabic-script runs."""

    def __init__(self, document, font_family: str) -> None:
        super().__init__(document)
        self._font_family = str(font_family).strip()

    def set_font_family(self, font_family: str) -> None:
        value = str(font_family).strip()
        if value == self._font_family:
            return
        self._font_family = value
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        """Keep base letters, joiners, and combining marks in one font run for correct diacritics."""
        if not self._font_family or not text:
            return

        run_start: int | None = None
        for offset, char in enumerate(text):
            if self._belongs_to_arabic_shaping_run(char, run_start is not None):
                if run_start is None:
                    run_start = offset
                continue
            if run_start is not None:
                self._set_font_run(run_start, offset - run_start)
                run_start = None

        if run_start is not None:
            self._set_font_run(run_start, len(text) - run_start)

    def _set_font_run(self, start: int, length: int) -> None:
        if length <= 0:
            return
        fmt = QTextCharFormat()
        try:
            fmt.setFontFamilies([self._font_family])
        except AttributeError:
            fmt.setFontFamily(self._font_family)
        self.setFormat(start, length, fmt)

    @classmethod
    def _belongs_to_arabic_shaping_run(cls, char: str, inside_run: bool) -> bool:
        if cls._is_arabic_script_character(char):
            return True
        if inside_run and char and unicodedata.combining(char):
            return True
        return False

    @staticmethod
    def _is_arabic_script_character(char: str) -> bool:
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
    _FALLBACK_FAMILIES = (
        "Noto Naskh Arabic",
        "Noto Sans Arabic",
        "Vazirmatn",
        "DejaVu Sans",
    )

    def __init__(self, editor_panel, app_settings, parent=None) -> None:
        self._editor_panel = editor_panel
        self._app_settings = app_settings
        self._parent = parent
        self._font_family = self.DEFAULT_FONT_FAMILY
        self._highlighters: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

        editor_panel.current_document_changed.connect(self._on_editor_context_changed)
        editor_panel.current_view_changed.connect(self._on_editor_context_changed)
        self.reload()

    def reload(self) -> None:
        requested = self._read_visual_persian_font_family(
            self._app_settings.settings_path
        )
        self._font_family = self._resolve_installed_family(requested)
        self._bind_current_editor()
        for highlighter in list(self._highlighters.values()):
            highlighter.set_font_family(self._font_family)

    def _on_editor_context_changed(self, *_args) -> None:
        self._bind_current_editor()

    def _bind_current_editor(self) -> None:
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
    def _resolve_installed_family(cls, requested: str) -> str:
        try:
            available = {str(name).casefold(): str(name) for name in QFontDatabase.families()}
        except Exception:
            return requested or cls.DEFAULT_FONT_FAMILY

        candidates = [requested, *cls._FALLBACK_FAMILIES]
        for candidate in candidates:
            value = str(candidate or "").strip()
            if not value:
                continue
            installed = available.get(value.casefold())
            if installed:
                return installed
        return requested or cls.DEFAULT_FONT_FAMILY

    @classmethod
    def _read_visual_persian_font_family(cls, settings_path: str | Path) -> str:
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
        return PersianVisualFontHighlighter._is_arabic_script_character(char)
