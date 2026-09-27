"""Per-file incremental spell-check orchestration for Source and Visual modes."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.core.spell.spell_check_candidate_extractor import (
    SpellCheckCandidateExtractor,
)
from nd_mind_mirror.core.spell.spell_check_engine import SpellCheckEngine
from nd_mind_mirror.core.spell.spell_check_language_detector import (
    SpellCheckLanguageDetector,
)
from nd_mind_mirror.core.spell.spell_check_preference_store import (
    SpellCheckPreferenceStore,
)
from nd_mind_mirror.ui.editor.spell.spell_check_highlighter import (
    SpellCheckHighlighter,
)


class SpellCheckController(QObject):
    """Run spell checking only for the active view and visible text window."""

    _DEBOUNCE_MS = 220
    _VIEWPORT_MARGIN_CHARS = 1200
    _MAX_SCAN_CHARS = 10000
    _MAX_VISIBLE_MARKS = 250
    _LANGUAGE_LABELS = {"en": "English", "de": "German", "fa": "Persian"}

    def __init__(self, editor, app_settings, parent=None) -> None:
        super().__init__(parent or editor)
        self._editor = editor
        self._source_path = Path(editor.source_path)
        self._app_settings = app_settings
        self._preferences = SpellCheckPreferenceStore(
            app_settings.session_settings_path
        )
        self._extractor = SpellCheckCandidateExtractor()
        self._language_detector = SpellCheckLanguageDetector()
        self._highlighter = SpellCheckHighlighter()
        self._engine: SpellCheckEngine | None = None
        self._enabled = self._preferences.is_enabled(self._source_path)
        self._language_mode = self._preferences.language(self._source_path)
        self._resolved_language: str | None = (
            None if self._language_mode == "auto" else self._language_mode
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._DEBOUNCE_MS)
        self._timer.timeout.connect(self._refresh)

        editor.document().contentsChanged.connect(self.schedule)
        editor.active_view_changed.connect(self.schedule)
        visual = editor._visual_editor
        visual.document().contentsChanged.connect(self.schedule)

        if self._enabled:
            QTimer.singleShot(0, self.schedule)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def language_mode(self) -> str:
        return self._language_mode

    @property
    def effective_language(self) -> str:
        return self._effective_language()

    def set_enabled(self, enabled: bool) -> None:
        value = bool(enabled)
        if value == self._enabled:
            return
        self._enabled = value
        self._preferences.set_enabled(self._source_path, value)
        if value:
            self.schedule()
            return
        self._timer.stop()
        self._clear_all()

    def toggle_enabled(self) -> None:
        self.set_enabled(not self._enabled)

    def set_language_mode(self, language: str) -> None:
        value = str(language).strip().casefold()
        if value not in {"auto", "en", "de", "fa"}:
            return
        self._language_mode = value
        self._resolved_language = None if value == "auto" else value
        self._preferences.set_language(self._source_path, value)
        if self._enabled:
            self.schedule()

    def remap_source_path(self, old_path: str | Path, new_path: str | Path) -> None:
        old_value = Path(old_path).expanduser().resolve()
        new_value = Path(new_path).expanduser().resolve()
        if old_value == new_value:
            self._source_path = new_value
            return
        self._preferences.remap(old_value, new_value)
        self._source_path = new_value
        self._enabled = self._preferences.is_enabled(new_value)
        self._language_mode = self._preferences.language(new_value)
        self._resolved_language = (
            None if self._language_mode == "auto" else self._language_mode
        )
        if self._enabled:
            self.schedule()
        else:
            self._clear_all()

    def schedule(self, *_args) -> None:
        if not self._enabled:
            return
        self._timer.start()

    def append_context_actions(
        self,
        menu,
        widget,
        position: int,
        *,
        source_mode: bool,
    ) -> list[tuple[object, Callable[[], None]]]:
        actions: list[tuple[object, Callable[[], None]]] = []
        menu.addSeparator()
        toggle = menu.addAction(
            "Disable spell check for this file"
            if self._enabled
            else "Enable spell check for this file"
        )
        actions.append((toggle, self.toggle_enabled))
        if not self._enabled:
            return actions

        language = self._effective_language()
        language_menu = menu.addMenu("Spell check language")
        detected_label = self._LANGUAGE_LABELS.get(language, language)
        language_options = (
            ("auto", f"Auto ({detected_label} detected)"),
            ("en", "English"),
            ("de", "German"),
            ("fa", "Persian"),
        )
        for value, label in language_options:
            action = language_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._language_mode == value)
            actions.append(
                (
                    action,
                    lambda selected=value: self.set_language_mode(selected),
                )
            )

        candidate = (
            self._extractor.source_word_at(
                widget.document().toPlainText(),
                position,
            )
            if source_mode
            else self._extractor.visual_word_at(widget.document(), position)
        )
        if candidate is None:
            return actions
        start, end, word = candidate
        engine = self._engine_instance()
        if engine.is_correct(word, language):
            return actions

        spelling_menu = menu.addMenu(f'Spelling: "{word}"')
        suggestions = engine.suggestions(word, language, limit=5)
        if not suggestions:
            empty_action = spelling_menu.addAction("No suggestions")
            empty_action.setEnabled(False)
        for suggestion in suggestions:
            action = spelling_menu.addAction(suggestion)
            actions.append(
                (
                    action,
                    lambda replacement=suggestion, target=widget,
                    left=start, right=end: self._replace_word(
                        target,
                        left,
                        right,
                        replacement,
                    ),
                )
            )

        language_label = self._LANGUAGE_LABELS.get(language, language)
        add_action = spelling_menu.addAction(
            f"Add to {language_label} dictionary"
        )
        actions.append(
            (
                add_action,
                lambda lang=language, value=word: self._add_word(lang, value),
            )
        )
        return actions

    @staticmethod
    def execute_context_action(
        chosen,
        actions: list[tuple[object, Callable[[], None]]],
    ) -> bool:
        for action, callback in actions:
            if chosen == action:
                callback()
                return True
        return False
    def _refresh(self) -> None:
        if not self._enabled:
            return
        if str(self._editor.edit_mode) == "visual":
            self._highlighter.clear(self._editor)
            self._refresh_visual()
            return
        self._highlighter.clear(self._editor._visual_editor)
        self._refresh_source()

    def _refresh_source(self) -> None:
        widget = self._editor
        text = widget.document().toPlainText()
        start, end = self._visible_bounds(widget)
        candidates = self._extractor.source_candidates(text, start, end)
        self._highlighter.apply(widget, self._misspelled_ranges(candidates))

    def _refresh_visual(self) -> None:
        widget = self._editor._visual_editor
        start, end = self._visible_bounds(widget)
        candidates = self._extractor.visual_candidates(
            widget.document(),
            start,
            end,
        )
        self._highlighter.apply(widget, self._misspelled_ranges(candidates))

    def _misspelled_ranges(
        self,
        candidates: list[tuple[int, int, str]],
    ) -> list[tuple[int, int]]:
        engine = self._engine_instance()
        language = self._effective_language()
        ranges: list[tuple[int, int]] = []
        for start, end, word in candidates:
            if engine.is_correct(word, language):
                continue
            ranges.append((start, end))
            if len(ranges) >= self._MAX_VISIBLE_MARKS:
                break
        return ranges

    def _effective_language(self) -> str:
        if self._language_mode != "auto":
            return self._language_mode
        if self._resolved_language is None:
            self._resolved_language = self._detect_document_language()
        return self._resolved_language

    def _detect_document_language(self) -> str:
        source_provider = getattr(self._editor, "canonical_source", None)
        source = (
            str(source_provider())
            if callable(source_provider)
            else str(self._editor.toPlainText())
        )
        words: list[str] = []
        for start, end in self._language_sample_ranges(len(source)):
            words.extend(
                word
                for _left, _right, word in self._extractor.source_candidates(
                    source,
                    start,
                    end,
                )
            )
        return self._language_detector.detect(
            words,
            self._engine_instance(),
        )

    @staticmethod
    def _language_sample_ranges(length: int) -> list[tuple[int, int]]:
        size = max(int(length), 0)
        if size <= 30000:
            return [(0, size)]
        window = 10000
        middle = size // 2
        return [
            (0, min(window, size)),
            (max(middle - window // 2, 0), min(middle + window // 2, size)),
            (max(size - window, 0), size),
        ]

    def _visible_bounds(self, widget) -> tuple[int, int]:
        viewport = widget.viewport()
        top = widget.cursorForPosition(QPoint(0, 0)).position()
        bottom = widget.cursorForPosition(
            QPoint(max(viewport.width() - 1, 0), max(viewport.height() - 1, 0))
        ).position()
        left = max(min(top, bottom) - self._VIEWPORT_MARGIN_CHARS, 0)
        maximum = max(widget.document().characterCount() - 1, 0)
        right = min(
            max(top, bottom) + self._VIEWPORT_MARGIN_CHARS,
            maximum,
        )
        if right - left > self._MAX_SCAN_CHARS:
            center = max(0, min((top + bottom) // 2, maximum))
            half = self._MAX_SCAN_CHARS // 2
            left = max(center - half, 0)
            right = min(left + self._MAX_SCAN_CHARS, maximum)
            left = max(right - self._MAX_SCAN_CHARS, 0)
        return left, max(right, left)

    def _engine_instance(self) -> SpellCheckEngine:
        if self._engine is None:
            self._engine = SpellCheckEngine(
                self._app_settings.data_root / "spell_check" / "dictionaries"
            )
        return self._engine

    def _replace_word(
        self,
        widget,
        start: int,
        end: int,
        replacement: str,
    ) -> None:
        cursor = QTextCursor(widget.document())
        cursor.setPosition(int(start))
        cursor.setPosition(int(end), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(str(replacement))
        self.schedule()

    def _add_word(self, language: str, word: str) -> None:
        if self._engine_instance().add_to_dictionary(language, word):
            self.schedule()

    def _clear_all(self) -> None:
        self._highlighter.clear(self._editor)
        self._highlighter.clear(self._editor._visual_editor)
