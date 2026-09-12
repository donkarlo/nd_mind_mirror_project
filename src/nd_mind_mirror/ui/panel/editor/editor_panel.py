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


class EditorPanel(EditorPanelCore):
    """Create editors and expose non-blocking autosave snapshots.

    Moderate LaTeX documents keep one complete canonical QTextDocument. Only
    genuinely large documents use SelectionLargeLatexEditor and its bounded
    Source window. This separation prevents the performance threshold from
    changing document ownership semantics.
    """

    _SOURCE_VIRTUALIZATION_THRESHOLD_CHARS = 1_000_000

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
            latex_editor_type = (
                SelectionLargeLatexEditor
                if len(content) >= self._SOURCE_VIRTUALIZATION_THRESHOLD_CHARS
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

        remembered_state = self._remembered_view_states.get(str(file_path))
        if remembered_state is not None:
            QTimer.singleShot(
                0,
                lambda item=editor, state=dict(remembered_state):
                item.restore_view_state(state),
            )

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

    def autosave_snapshots(
        self,
    ) -> list[tuple[Path, int, tuple[str, ...]]]:
        """Capture modified documents without joining windowed large sources."""
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
        """Return True only if no edit occurred after an autosave snapshot."""
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
