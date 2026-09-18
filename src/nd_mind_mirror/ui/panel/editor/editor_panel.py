from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.bookmark.selection_large_latex_editor import (
    SelectionLargeLatexEditor,
)
from nd_mind_mirror.ui.editor.bookmark.selection_latex_editor import (
    SelectionLatexEditor,
)
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.panel.editor.editor_panel_core import EditorPanel as EditorPanelCore
from nd_mind_mirror.core.bookmark.range.range_bookmark_migrator import (
    RangeBookmarkMigrator,
)


class EditorPanel(EditorPanelCore):
    """Create editors and preserve per-tab editing state for normal/large text."""

    def __init__(self, completions, app_settings, parent=None) -> None:
        self._active_editor: TextEditor | None = None
        self._pending_view_state_restore_paths: set[str] = set()
        super().__init__(completions, app_settings, parent)

    def apply_settings(self, app_settings) -> None:
        super().apply_settings(app_settings)
        for editor in list(self._paths):
            if isinstance(editor, TextEditor):
                self._apply_cursor_preferences(editor)

    def set_bookmarks(self, data: dict | None) -> None:
        """Migrate all persisted bookmark groups into the range-only repository."""
        self._bookmarks_by_path = {}
        if not isinstance(data, dict):
            return

        migrator = RangeBookmarkMigrator()
        for raw_path, raw_bookmarks in data.items():
            if not isinstance(raw_bookmarks, list):
                continue
            try:
                path = Path(raw_path).expanduser().resolve()
                source = path.read_text(encoding="utf-8")
            except (OSError, TypeError, ValueError, UnicodeError):
                continue

            migrated = migrator.migrate(
                [item for item in raw_bookmarks if isinstance(item, dict)],
                source,
            )
            if migrated:
                self._bookmarks_by_path[str(path)] = [
                    item.to_dict() for item in migrated
                ]

        for editor, path in list(self._paths.items()):
            if isinstance(editor, LatexEditor):
                editor.set_bookmarks(
                    self._bookmarks_by_path.get(str(path), [])
                )

    def set_view_states(self, states: dict | None) -> None:
        """Load persisted view states while retaining LaTeX Source/Visual fields."""
        self._remembered_view_states = {}
        if not isinstance(states, dict):
            return

        integer_fields = {
            "cursor",
            "vertical",
            "horizontal",
            "active_source_line",
            "active_source_column",
            "visible_source_line",
            "visible_source_column",
        }
        for raw_path, raw_state in states.items():
            if not isinstance(raw_state, dict):
                continue
            try:
                path = str(Path(str(raw_path)).expanduser().resolve())
                state = dict(raw_state)
                for key in integer_fields:
                    if key in state:
                        state[key] = int(state[key])
                if "edit_mode" in state:
                    state["edit_mode"] = (
                        "visual"
                        if str(state["edit_mode"]).strip().lower() == "visual"
                        else "source"
                    )
                self._remembered_view_states[path] = state
            except (TypeError, ValueError, OSError):
                continue

        self._pending_view_state_restore_paths = set(
            self._remembered_view_states
        )

    def open_file(
        self,
        path: str | Path,
        content: str,
        select: bool = True,
    ) -> bool:
        file_path = Path(path).expanduser().resolve()

        existing = self._index_for_path(file_path)
        if existing >= 0:
            if select:
                self._tabs.setCurrentIndex(existing)
                editor = self._tabs.widget(existing)
                if isinstance(editor, TextEditor):
                    editor.setFocus()
            return True

        while self._tabs.count() >= self._max_tabs:
            removable = self._least_recently_used_unmodified_index()
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
        elif file_path.suffix.lower() in {".tex", ".tikz"}:
            large_document_threshold = (
                self._app_settings.editor_source_large_document_threshold_chars
            )
            latex_editor_type = (
                SelectionLargeLatexEditor
                if len(content) >= large_document_threshold
                else SelectionLatexEditor
            )
            editor = latex_editor_type(
                completions=self._completions,
                source_path=file_path,
                app_settings=self._app_settings,
                parent=self,
            )
        else:
            editor = GenericTextEditor(
                source_path=file_path,
                app_settings=self._app_settings,
                parent=self,
            )

        editor.set_content(content)
        if isinstance(editor, LatexEditor):
            editor.set_bookmarks(
                self._bookmarks_by_path.get(str(file_path), [])
            )
        self._apply_cursor_preferences(editor)

        self._paths[editor] = file_path

        editor.content_changed.connect(
            lambda text, item=editor: self._on_editor_content_changed(item, text)
        )
        editor.modification_changed.connect(
            lambda modified, item=editor: self._on_editor_modification_changed(
                item, modified
            )
        )
        if isinstance(editor, LatexEditor):
            editor.active_cursor_changed.connect(
                lambda item=editor: self._on_editor_cursor_changed(item)
            )
            editor.active_view_changed.connect(
                lambda item=editor: self._on_editor_view_changed(item)
            )
            editor.bookmarks_changed.connect(
                lambda bookmarks, item=editor: self._on_editor_bookmarks_changed(
                    item, bookmarks
                )
            )
        else:
            editor.cursorPositionChanged.connect(
                lambda item=editor: self._on_editor_cursor_changed(item)
            )
            editor.verticalScrollBar().valueChanged.connect(
                lambda value, item=editor: self._on_editor_view_changed(item)
            )
        editor.horizontalScrollBar().valueChanged.connect(
            lambda value, item=editor: self._remember_editor_view_state(item)
        )

        index = self._tabs.addTab(editor, "")
        self._activation_counter += 1
        self._last_activated[editor] = self._activation_counter
        self._tabs.setTabToolTip(index, str(file_path))
        self._refresh_tab_titles()

        if select:
            self._tabs.setCurrentIndex(index)
            editor.setFocus()

        return True

    def _on_current_changed(self, index: int) -> None:
        editor = self.current_editor()
        previous_editor = self._active_editor
        if previous_editor is not None and previous_editor is not editor:
            self._remember_editor_view_state(previous_editor)

        super()._on_current_changed(index)

        self._active_editor = editor
        if editor is None:
            return
        path = self._paths.get(editor)
        if path is None:
            return

        self._apply_cursor_preferences(editor)
        self._restore_persisted_view_state_once(editor, path)

    def _restore_persisted_view_state_once(
        self,
        editor: TextEditor,
        path: Path,
    ) -> None:
        """Restore session state only on the first activation of this tab.

        A live QTextEdit already owns its cursor and scrollbars while it remains
        open. Reapplying the persisted session snapshot on every tab switch
        overwrites that live state and makes Ctrl+Tab appear to lose the caret.
        """
        key = str(path)
        if key not in self._pending_view_state_restore_paths:
            return
        self._pending_view_state_restore_paths.discard(key)
        remembered_state = self._remembered_view_states.get(key)
        if remembered_state is None:
            return
        QTimer.singleShot(
            0,
            lambda item=editor, expected_path=path, state=dict(remembered_state):
            self._restore_editor_view_state(item, expected_path, state),
        )

    def _on_editor_cursor_changed(self, editor: TextEditor) -> None:
        self._remember_editor_view_state(editor)
        super()._on_editor_cursor_changed(editor)

    def _remember_editor_view_state(self, editor: TextEditor) -> None:
        path = self._paths.get(editor)
        if path is None:
            return
        self._remembered_view_states[str(path)] = dict(editor.view_state())

    def _restore_editor_view_state(
        self,
        editor: TextEditor,
        expected_path: Path,
        state: dict[str, object],
    ) -> None:
        if self.current_editor() is not editor:
            return
        if self._paths.get(editor) != expected_path:
            return
        editor.restore_view_state(state)

    def _apply_cursor_preferences(self, editor: TextEditor) -> None:
        editor.apply_cursor_preferences(
            color=self._app_settings.editor_cursor_color,
            size_percent=self._app_settings.editor_cursor_size_percent,
            thickness=self._app_settings.editor_cursor_thickness,
        )

    def replace_bookmarks_for_path(
        self,
        path: str | Path,
        bookmarks: list[dict[str, object]],
    ) -> None:
        """Update persisted and open-editor bookmark state through one repository."""
        target = Path(path).expanduser().resolve()
        items = [dict(item) for item in bookmarks if isinstance(item, dict)]
        if items:
            self._bookmarks_by_path[str(target)] = items
        else:
            self._bookmarks_by_path.pop(str(target), None)

        index = self._index_for_path(target)
        if index >= 0:
            editor = self._tabs.widget(index)
            if isinstance(editor, LatexEditor):
                editor.set_bookmarks(items)

        self.bookmarks_changed.emit(self.bookmarks())

    def remove_range_bookmark(
        self,
        path: str | Path,
        bookmark_id: str,
    ) -> None:
        target = Path(path).expanduser().resolve()
        current = self.bookmarks().get(str(target), [])
        self.replace_bookmarks_for_path(
            target,
            [
                item
                for item in current
                if str(item.get("id", "")) != str(bookmark_id)
            ],
        )

    def remove_all_range_bookmarks(self) -> None:
        for editor in list(self._paths):
            if isinstance(editor, LatexEditor):
                clear = getattr(editor, "clear_range_bookmarks", None)
                if callable(clear):
                    clear()
        self._bookmarks_by_path.clear()
        self.bookmarks_changed.emit({})

    def autosave_snapshots(
        self,
    ) -> list[tuple[Path, int, tuple[str, ...]]]:
        result: list[tuple[Path, int, tuple[str, ...]]] = []
        for editor, path in list(self._paths.items()):
            if not isinstance(editor, TextEditor):
                continue
            if not editor.document().isModified():
                continue

            snapshot = getattr(editor, "autosave_snapshot", None)
            if callable(snapshot):
                revision, pieces = snapshot()
                result.append(
                    (
                        Path(path).expanduser().resolve(),
                        int(revision),
                        tuple(pieces),
                    )
                )
                continue

            result.append(
                (
                    Path(path).expanduser().resolve(),
                    int(editor.document().revision()),
                    (editor.toPlainText(),),
                )
            )
        return result

    def autosave_revision_matches(
        self,
        path: str | Path,
        revision: int,
    ) -> bool:
        index = self._index_for_path(Path(path).expanduser().resolve())
        if index < 0:
            return False
        editor = self._tabs.widget(index)
        if not isinstance(editor, TextEditor):
            return False

        current_revision = getattr(editor, "autosave_revision", None)
        if callable(current_revision):
            return int(current_revision()) == int(revision)
        return int(editor.document().revision()) == int(revision)

