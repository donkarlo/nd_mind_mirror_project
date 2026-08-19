from pathlib import Path
import re

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QTabWidget,
)

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.panel.base.panel import Panel
from nd_mind_mirror.ui.toolbar.editor.latex_format_toolbar import (
    LatexFormatToolbar,
)
from nd_mind_mirror.ui.toolbar.editor.editor_find_replace_bar import (
    EditorFindReplaceBar,
)


class EditorPanel(Panel):
    current_document_changed = Signal(str, str)
    current_content_changed = Signal(str, str)
    current_modification_changed = Signal(str, bool)
    current_cursor_changed = Signal(str, int, int)
    current_view_changed = Signal(str, int, int)
    capacity_reached = Signal(str)
    tab_close_requested = Signal(int, str, bool)
    settings_apply_requested = Signal()

    _TAB_LABEL_LENGTH = 24
    _TAB_WIDTH = 220

    def __init__(
        self,
        completions: list[str],
        app_settings: YamlSettings,
        parent=None,
    ) -> None:
        super().__init__("LaTeX Editor", parent)

        self._completions = completions
        self._app_settings = app_settings
        self._max_tabs = app_settings.editor_max_open_tabs
        self._activation_counter = 0
        self._last_activated: dict[TextEditor, int] = {}
        self._paths: dict[
            TextEditor,
            Path,
        ] = {}
        self._remembered_view_states: dict[str, dict[str, int]] = {}
        self._find_matches: list[tuple[int, int]] = []
        self._find_current_index = -1

        self.setMinimumWidth(120)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel(
            "LaTeX Editor",
            self,
        )

        self._format_toolbar = LatexFormatToolbar(self)
        self._format_toolbar.bold_requested.connect(
            self.bold_current_selection
        )
        self._format_toolbar.highlight_requested.connect(
            self.highlight_current_selection
        )
        self._format_toolbar.apply_settings_requested.connect(
            self.settings_apply_requested.emit
        )
        self._format_toolbar.set_mode(
            latex_enabled=False,
            settings_enabled=False,
        )

        self._find_bar = EditorFindReplaceBar(self)
        self._find_bar.query_changed.connect(self._refresh_find_matches)
        self._find_bar.next_requested.connect(self.find_next)
        self._find_bar.previous_requested.connect(self.find_previous)
        self._find_bar.replace_requested.connect(self.replace_current_match)
        self._find_bar.close_requested.connect(self.hide_find_replace)
        self._find_escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._find_escape_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._find_escape_shortcut.activated.connect(self.hide_find_replace)
        self._find_escape_shortcut.setEnabled(False)

        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)
        self._tabs.setMovable(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setMinimumWidth(0)
        self._tabs.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self._tabs.setElideMode(
            Qt.TextElideMode.ElideNone
        )
        self._tabs.tabBar().setExpanding(False)
        self._tabs.tabBar().setUsesScrollButtons(
            True
        )
        self._tabs.tabBar().setStyleSheet(
            "QTabBar::tab {"
            f"min-width: {self._TAB_WIDTH}px;"
            f"max-width: {self._TAB_WIDTH}px;"
            "}"
        )

        self._tabs.currentChanged.connect(
            self._on_current_changed
        )
        self._tabs.tabCloseRequested.connect(
            self._on_tab_close_requested
        )
        self._tabs.tabBar().tabMoved.connect(
            self._on_tab_moved
        )

        self.panel_layout.addWidget(
            self._label
        )
        self.panel_layout.addWidget(
            self._format_toolbar
        )
        self.panel_layout.addWidget(
            self._find_bar
        )
        self.panel_layout.addWidget(
            self._tabs,
            1,
        )

    def apply_settings(
        self,
        app_settings: YamlSettings,
    ) -> None:
        self._app_settings = app_settings
        self._max_tabs = app_settings.editor_max_open_tabs

        for editor in self._paths:
            editor.apply_settings(
                app_settings
            )

    def open_file(
        self,
        path: str | Path,
        content: str,
        select: bool = True,
    ) -> bool:
        file_path = Path(
            path
        ).expanduser().resolve()

        existing = self._index_for_path(
            file_path
        )

        if existing >= 0:
            if select:
                self._tabs.setCurrentIndex(
                    existing
                )
                editor = self._tabs.widget(
                    existing
                )
                if isinstance(
                    editor,
                    TextEditor,
                ):
                    editor.setFocus()
            return True

        while self._tabs.count() >= self._max_tabs:
            removable = (
                self._least_recently_used_unmodified_index()
            )

            if removable < 0:
                self.capacity_reached.emit(
                    f"The editor tab limit is {self._max_tabs}, and all "
                    "open tabs that could be closed automatically contain "
                    "unsaved changes. Save or close one before opening "
                    "another file."
                )
                return False

            self.close_tab(removable)

        if file_path.suffix.lower() in {".yaml", ".yml"}:
            editor = YamlEditor(
                source_path=file_path,
                app_settings=self._app_settings,
                parent=self,
            )
        else:
            editor = LatexEditor(
                completions=self._completions,
                source_path=file_path,
                app_settings=self._app_settings,
                parent=self,
            )
        editor.set_content(
            content
        )

        remembered_state = self._remembered_view_states.get(
            str(file_path)
        )
        if remembered_state is not None:
            QTimer.singleShot(
                0,
                lambda item=editor, state=dict(remembered_state):
                item.restore_view_state(state),
            )

        self._paths[editor] = file_path

        editor.content_changed.connect(
            lambda text, item=editor:
            self._on_editor_content_changed(
                item,
                text,
            )
        )
        editor.modification_changed.connect(
            lambda modified, item=editor:
            self._on_editor_modification_changed(
                item,
                modified,
            )
        )
        editor.cursorPositionChanged.connect(
            lambda item=editor:
            self._on_editor_cursor_changed(item)
        )
        editor.verticalScrollBar().valueChanged.connect(
            lambda value, item=editor:
            self._on_editor_view_changed(item)
        )
        editor.horizontalScrollBar().valueChanged.connect(
            lambda value, item=editor:
            self._remember_editor_view_state(item)
        )

        index = self._tabs.addTab(
            editor,
            "",
        )
        self._activation_counter += 1
        self._last_activated[editor] = self._activation_counter
        self._tabs.setTabToolTip(
            index,
            str(file_path),
        )

        self._refresh_tab_titles()

        if select:
            self._tabs.setCurrentIndex(
                index
            )
            editor.setFocus()

        return True

    def close_tab(
        self,
        index: int,
    ) -> None:
        if (
            index < 0
            or index >= self._tabs.count()
        ):
            return

        editor = self._tabs.widget(
            index
        )
        path = self._paths.get(editor)
        if isinstance(editor, TextEditor) and path is not None:
            self._remembered_view_states[str(path)] = editor.view_state()
        self._paths.pop(
            editor,
            None,
        )
        self._last_activated.pop(
            editor,
            None,
        )

        self._tabs.removeTab(
            index
        )
        editor.deleteLater()

        self._refresh_tab_titles()

    def close_paths_under(
        self,
        path: str | Path,
    ) -> None:
        parent_path = Path(
            path
        ).expanduser().resolve()

        indices = []

        for index in range(
            self._tabs.count()
        ):
            candidate = self.path_at(
                index
            )

            if (
                candidate is not None
                and self._is_same_or_child(
                    candidate,
                    parent_path,
                )
            ):
                indices.append(
                    index
                )

        for index in reversed(
            indices
        ):
            self.close_tab(
                index
            )

    def rename_paths_under(
        self,
        old_path: str | Path,
        new_path: str | Path,
    ) -> None:
        old_root = Path(
            old_path
        ).expanduser().resolve()
        new_root = Path(
            new_path
        ).expanduser().resolve()

        current_editor = self.current_editor()
        current_changed = False

        for editor, path in list(
            self._paths.items()
        ):
            try:
                relative = path.relative_to(
                    old_root
                )
            except ValueError:
                continue

            updated = (
                new_root / relative
            ).resolve()

            self._paths[
                editor
            ] = updated
            editor.set_source_path(
                updated
            )

            if editor is current_editor:
                current_changed = True

        remembered_updates: dict[str, dict[str, int]] = {}
        remembered_remove: list[str] = []
        for raw_path, state in self._remembered_view_states.items():
            candidate = Path(raw_path)
            try:
                relative = candidate.relative_to(old_root)
            except ValueError:
                continue
            remembered_remove.append(raw_path)
            remembered_updates[str((new_root / relative).resolve())] = state
        for raw_path in remembered_remove:
            self._remembered_view_states.pop(raw_path, None)
        self._remembered_view_states.update(remembered_updates)

        self._refresh_tab_titles()

        if (
            current_changed
            and current_editor is not None
        ):
            current_path = self._paths.get(
                current_editor
            )

            if current_path is not None:
                self._label.setText(
                    f"LaTeX Editor — {current_path}"
                )
                self.current_document_changed.emit(
                    str(current_path),
                    current_editor.toPlainText(),
                )

    def bold_current_selection(self) -> None:
        editor = self.current_editor()
        if isinstance(editor, LatexEditor):
            editor.bold_selection()

    def highlight_current_selection(self, color: str) -> None:
        editor = self.current_editor()
        if isinstance(editor, LatexEditor):
            editor.highlight_selection(color)

    def show_find_replace(self, replace_mode: bool = False) -> None:
        editor = self.current_editor()
        if not isinstance(editor, TextEditor):
            return
        selected = editor.textCursor().selectedText().replace("\u2029", "\n")
        self._find_bar.show_for_mode(
            replace_mode=replace_mode,
            initial_query=selected if "\n" not in selected else "",
        )
        self._find_escape_shortcut.setEnabled(True)
        self._refresh_find_matches(self._find_bar.query)

    def hide_find_replace(self) -> None:
        if not self._find_bar.isVisible():
            return
        self._find_bar.hide()
        self._find_escape_shortcut.setEnabled(False)
        self._find_matches = []
        self._find_current_index = -1
        for editor in self._paths:
            editor.clear_search_highlights()
        editor = self.current_editor()
        if isinstance(editor, TextEditor):
            editor.setFocus()

    def find_next(self) -> None:
        if not self._find_matches:
            self._refresh_find_matches(self._find_bar.query)
        if not self._find_matches:
            return
        self._find_current_index = (self._find_current_index + 1) % len(self._find_matches)
        self._activate_find_match()

    def find_previous(self) -> None:
        if not self._find_matches:
            self._refresh_find_matches(self._find_bar.query)
        if not self._find_matches:
            return
        self._find_current_index = (self._find_current_index - 1) % len(self._find_matches)
        self._activate_find_match()

    def replace_current_match(self, replacement: str) -> None:
        editor = self.current_editor()
        if not isinstance(editor, TextEditor) or not self._find_matches:
            return
        if self._find_current_index < 0:
            self._find_current_index = 0
        start, end = self._find_matches[self._find_current_index]
        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.beginEditBlock()
        cursor.insertText(str(replacement))
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        position = cursor.position()
        self._refresh_find_matches(self._find_bar.query)
        if self._find_matches:
            self._find_current_index = next(
                (i for i, (candidate_start, _) in enumerate(self._find_matches) if candidate_start >= position),
                0,
            )
            self._activate_find_match()

    def _refresh_find_matches(self, query: str | None = None) -> None:
        editor = self.current_editor()
        if not isinstance(editor, TextEditor):
            self._find_matches = []
            self._find_current_index = -1
            self._find_bar.set_match_status(0, 0)
            return

        query_text = self._find_bar.query if query is None else str(query)
        if not query_text:
            self._find_matches = []
            self._find_current_index = -1
            editor.clear_search_highlights()
            self._find_bar.set_match_status(0, 0)
            return

        source = editor.toPlainText()
        self._find_matches = [
            (match.start(), match.end())
            for match in re.finditer(re.escape(query_text), source, re.IGNORECASE)
        ]
        if not self._find_matches:
            self._find_current_index = -1
            editor.clear_search_highlights()
            self._find_bar.set_match_status(0, 0)
            return

        cursor_position = editor.textCursor().position()
        self._find_current_index = next(
            (i for i, (start, end) in enumerate(self._find_matches) if start <= cursor_position <= end),
            next(
                (i for i, (start, _) in enumerate(self._find_matches) if start >= cursor_position),
                0,
            ),
        )
        self._apply_find_highlights()

    def _apply_find_highlights(self) -> None:
        editor = self.current_editor()
        if not isinstance(editor, TextEditor):
            return
        editor.set_search_highlights(
            self._find_matches,
            self._find_current_index,
        )
        total = len(self._find_matches)
        self._find_bar.set_match_status(
            self._find_current_index + 1 if total else 0,
            total,
        )

    def _activate_find_match(self) -> None:
        editor = self.current_editor()
        if not isinstance(editor, TextEditor) or not self._find_matches:
            return
        self._find_current_index %= len(self._find_matches)
        start, end = self._find_matches[self._find_current_index]
        cursor = QTextCursor(editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()
        self._apply_find_highlights()

    def set_view_states(self, states: dict | None) -> None:
        self._remembered_view_states = {}
        if not isinstance(states, dict):
            return
        for raw_path, raw_state in states.items():
            if not isinstance(raw_state, dict):
                continue
            try:
                path = str(Path(str(raw_path)).expanduser().resolve())
                self._remembered_view_states[path] = {
                    "cursor": int(raw_state.get("cursor", 0)),
                    "vertical": int(raw_state.get("vertical", 0)),
                    "horizontal": int(raw_state.get("horizontal", 0)),
                }
            except (TypeError, ValueError, OSError):
                continue

    def view_states(self) -> dict[str, dict[str, int]]:
        states = dict(self._remembered_view_states)
        for editor, path in self._paths.items():
            states[str(path)] = editor.view_state()
        return states

    def format_current_document(
        self,
    ) -> None:
        editor = self.current_editor()

        if editor is None:
            return

        editor.format_document()

    def go_to_line(self, line_number: int) -> None:
        editor = self.current_editor()
        if editor is None:
            return
        editor.go_to_line(line_number)

    def content_at(
        self,
        index: int,
    ) -> str:
        if (
            index < 0
            or index >= self._tabs.count()
        ):
            return ""

        editor = self._tabs.widget(
            index
        )

        if isinstance(
            editor,
            TextEditor,
        ):
            return editor.toPlainText()

        return ""

    def path_at(
        self,
        index: int,
    ) -> Path | None:
        if (
            index < 0
            or index >= self._tabs.count()
        ):
            return None

        editor = self._tabs.widget(
            index
        )
        return self._paths.get(
            editor
        )

    def activate_path(
        self,
        path: str | Path,
    ) -> bool:
        index = self._index_for_path(
            Path(
                path
            ).expanduser().resolve()
        )

        if index < 0:
            return False

        self._tabs.setCurrentIndex(
            index
        )

        editor = self._tabs.widget(
            index
        )

        if isinstance(
            editor,
            TextEditor,
        ):
            editor.setFocus()

        return True

    def current_path(
        self,
    ) -> Path | None:
        editor = self.current_editor()

        if editor is None:
            return None

        return self._paths.get(
            editor
        )

    def current_editor(
        self,
    ) -> TextEditor | None:
        widget = self._tabs.currentWidget()

        if isinstance(
            widget,
            TextEditor,
        ):
            return widget

        return None

    def current_content(
        self,
    ) -> str:
        editor = self.current_editor()

        if editor is None:
            return ""

        return editor.toPlainText()

    def open_paths(
        self,
    ) -> list[Path]:
        result: list[Path] = []

        for index in range(
            self._tabs.count()
        ):
            path = self.path_at(index)
            if path is not None:
                result.append(path)

        return result

    def content_for_path(
        self,
        path: str | Path,
    ) -> str | None:
        file_path = Path(
            path
        ).expanduser().resolve()
        index = self._index_for_path(
            file_path
        )

        if index < 0:
            return None

        editor = self._tabs.widget(index)
        if not isinstance(editor, TextEditor):
            return None

        return editor.toPlainText()

    def replace_content_from_disk(
        self,
        path: str | Path,
        content: str,
    ) -> bool:
        file_path = Path(
            path
        ).expanduser().resolve()
        index = self._index_for_path(
            file_path
        )

        if index < 0:
            return False

        editor = self._tabs.widget(index)
        if not isinstance(editor, TextEditor):
            return False

        cursor = editor.textCursor()
        position = cursor.position()
        vertical = editor.verticalScrollBar().value()
        horizontal = editor.horizontalScrollBar().value()

        editor.set_content(content)

        restored = editor.textCursor()
        restored.setPosition(
            min(
                position,
                max(
                    editor.document().characterCount() - 1,
                    0,
                ),
            )
        )
        editor.setTextCursor(restored)
        editor.verticalScrollBar().setValue(vertical)
        editor.horizontalScrollBar().setValue(horizontal)
        self._refresh_tab_titles()
        return True

    def recent_paths(
        self,
    ) -> list[str]:
        paths = []

        for index in range(
            self._tabs.count()
        ):
            editor = self._tabs.widget(
                index
            )
            path = self._paths.get(
                editor
            )

            if path is not None:
                paths.append(
                    str(path)
                )

        return paths[
            -self._max_tabs:
        ]

    def modified_documents(
        self,
    ) -> list[tuple[Path, str]]:
        result = []

        for editor, path in self._paths.items():
            if (
                editor.document()
                .isModified()
            ):
                result.append(
                    (
                        path,
                        editor.toPlainText(),
                    )
                )

        return result

    def mark_saved(
        self,
        path: str | Path,
    ) -> None:
        index = self._index_for_path(
            Path(
                path
            ).expanduser().resolve()
        )

        if index < 0:
            return

        editor = self._tabs.widget(
            index
        )

        if isinstance(
            editor,
            TextEditor,
        ):
            editor.mark_saved()

        self._refresh_tab_titles()

    def is_current_modified(
        self,
    ) -> bool:
        editor = self.current_editor()

        return bool(
            editor
            and editor.document().isModified()
        )

    def _index_for_path(
        self,
        path: Path,
    ) -> int:
        for index in range(
            self._tabs.count()
        ):
            editor = self._tabs.widget(
                index
            )

            if self._paths.get(
                editor
            ) == path:
                return index

        return -1

    def _least_recently_used_unmodified_index(
        self,
    ) -> int:
        candidates: list[tuple[int, int]] = []

        for index in range(self._tabs.count()):
            editor = self._tabs.widget(index)
            if (
                isinstance(editor, TextEditor)
                and not editor.document().isModified()
            ):
                candidates.append(
                    (self._last_activated.get(editor, 0), index)
                )

        if not candidates:
            return -1

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def request_close_current_tab(self) -> None:
        index = self._tabs.currentIndex()
        if index >= 0:
            self._on_tab_close_requested(index)

    def _on_current_changed(
        self,
        index: int,
    ) -> None:
        editor = self.current_editor()
        path = self.current_path()

        self._refresh_tab_titles()

        if (
            editor is None
            or path is None
        ):
            if self._find_bar.isVisible():
                self.hide_find_replace()
            self._label.setText(
                "LaTeX Editor"
            )
            self._format_toolbar.set_mode(
                latex_enabled=False,
                settings_enabled=False,
            )
            return

        self._label.setText(
            f"LaTeX Editor — {path}"
        )
        is_settings = False
        try:
            is_settings = (
                path.resolve()
                == self._app_settings.settings_path.resolve()
            )
        except OSError:
            is_settings = False

        self._format_toolbar.set_mode(
            latex_enabled=isinstance(editor, LatexEditor),
            settings_enabled=is_settings,
        )
        if self._find_bar.isVisible():
            self._refresh_find_matches(self._find_bar.query)
        self._activation_counter += 1
        self._last_activated[editor] = self._activation_counter
        editor.setFocus()

        self.current_document_changed.emit(
            str(path),
            editor.toPlainText(),
        )
        self._emit_cursor_position(editor, path)

    def _on_editor_content_changed(
        self,
        editor: TextEditor,
        text: str,
    ) -> None:
        if editor is not self.current_editor():
            return

        path = self._paths.get(
            editor
        )

        if path is not None:
            self.current_content_changed.emit(
                str(path),
                text,
            )

        if self._find_bar.isVisible():
            QTimer.singleShot(
                0,
                lambda: self._refresh_find_matches(self._find_bar.query),
            )

    def _on_editor_cursor_changed(
        self,
        editor: TextEditor,
    ) -> None:
        if editor is not self.current_editor():
            return

        path = self._paths.get(editor)
        if path is None or path.suffix.lower() != ".tex":
            return

        self._emit_cursor_position(editor, path)

    def _emit_cursor_position(
        self,
        editor: TextEditor,
        path: Path,
    ) -> None:
        if path.suffix.lower() != ".tex":
            return

        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        self.current_cursor_changed.emit(
            str(path),
            line,
            column,
        )

    def _remember_editor_view_state(
        self,
        editor: TextEditor,
    ) -> None:
        path = self._paths.get(editor)
        if path is None:
            return
        self._remembered_view_states[str(path)] = editor.view_state()

    def _on_editor_view_changed(
        self,
        editor: TextEditor,
    ) -> None:
        self._remember_editor_view_state(editor)
        if editor is not self.current_editor():
            return

        path = self._paths.get(editor)
        if path is None or path.suffix.lower() != ".tex":
            return

        line, column = editor.first_visible_source_position()
        self.current_view_changed.emit(
            str(path),
            line,
            column,
        )

    def _on_editor_modification_changed(
        self,
        editor: TextEditor,
        modified: bool,
    ) -> None:
        self._refresh_tab_titles()

        if editor is not self.current_editor():
            return

        path = self._paths.get(
            editor
        )

        if path is not None:
            self.current_modification_changed.emit(
                str(path),
                modified,
            )

    def _on_tab_close_requested(
        self,
        index: int,
    ) -> None:
        path = self.path_at(
            index
        )

        if path is None:
            return

        editor = self._tabs.widget(
            index
        )
        modified = (
            isinstance(
                editor,
                TextEditor,
            )
            and editor.document().isModified()
        )

        self.tab_close_requested.emit(
            index,
            str(path),
            modified,
        )

    def _on_tab_moved(
        self,
        from_index: int,
        to_index: int,
    ) -> None:
        self._refresh_tab_titles()

    def _refresh_tab_titles(
        self,
    ) -> None:
        paths = []

        for index in range(
            self._tabs.count()
        ):
            path = self.path_at(
                index
            )

            if path is not None:
                paths.append(
                    path
                )

        labels = self._unique_hierarchical_labels(
            paths
        )

        for index, path in enumerate(
            paths
        ):
            editor = self._tabs.widget(
                index
            )
            modified = (
                isinstance(
                    editor,
                    TextEditor,
                )
                and editor.document().isModified()
            )

            label = labels[path][
                :self._TAB_LABEL_LENGTH
            ]

            if modified:
                label += " *"

            self._tabs.setTabText(
                index,
                label,
            )
            self._tabs.setTabToolTip(
                index,
                str(path),
            )

    def _unique_hierarchical_labels(
        self,
        paths: list[Path],
    ) -> dict[Path, str]:
        result = {}
        groups: dict[
            str,
            list[Path],
        ] = {}

        for path in paths:
            groups.setdefault(
                path.name,
                [],
            ).append(
                path
            )

        for filename, group in groups.items():
            if len(group) == 1:
                result[
                    group[0]
                ] = filename
                continue

            unresolved = set(
                group
            )
            depth = 2

            while unresolved:
                candidate_map: dict[
                    str,
                    list[Path],
                ] = {}

                for path in unresolved:
                    parts = path.parts
                    usable_depth = min(
                        depth,
                        len(parts),
                    )
                    candidate = "/".join(
                        parts[
                            -usable_depth:
                        ]
                    )
                    candidate_map.setdefault(
                        candidate,
                        [],
                    ).append(
                        path
                    )

                next_unresolved = set()

                for (
                    candidate,
                    candidate_paths,
                ) in candidate_map.items():
                    if len(
                        candidate_paths
                    ) == 1:
                        result[
                            candidate_paths[0]
                        ] = candidate
                    else:
                        next_unresolved.update(
                            candidate_paths
                        )

                if (
                    next_unresolved == unresolved
                    and depth
                    > max(
                        len(path.parts)
                        for path in unresolved
                    )
                ):
                    for path in unresolved:
                        result[
                            path
                        ] = str(path)
                    break

                unresolved = (
                    next_unresolved
                )
                depth += 1

        return result

    def _is_same_or_child(
        self,
        candidate: Path,
        parent: Path,
    ) -> bool:
        if candidate == parent:
            return True

        try:
            candidate.relative_to(
                parent
            )
            return True
        except ValueError:
            return False
