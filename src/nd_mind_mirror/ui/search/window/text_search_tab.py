"""Text-in-files search tab with exact source-location navigation."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.ui.search.thread.text_file_search_thread import TextFileSearchThread
from nd_mind_mirror.ui.search.window.search_scope_picker import SearchScopePicker


class TextSearchTab(QWidget):
    """Search literal text recursively and present every occurrence hierarchically."""

    location_selected = Signal(str, int, int)

    _LOCATION_ROLE = int(Qt.ItemDataRole.UserRole) + 20
    _HIT_ROLE = int(Qt.ItemDataRole.UserRole) + 21
    _SESSION_QUERY_KEY = "search/text/query"
    _SESSION_ROOT_KEY = "search/text/root_path"

    def __init__(
        self,
        default_root_path: str | Path,
        max_results: int,
        debounce_ms: int,
        ignore_file_path: str | Path,
        tree_indent_width: int,
        session_settings=None,
        parent=None,
    ) -> None:
        """Initialize the text-in-files search tab and persisted state."""
        super().__init__(parent)
        self._default_root_path = self._validated_root(default_root_path)
        self._max_results = max(int(max_results), 1)
        self._ignore_file_path = Path(ignore_file_path).expanduser().resolve()
        self._session_settings = session_settings
        self._generation = 0
        self._threads: list[TextFileSearchThread] = []

        initial_root = self._load_root()
        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Text to find inside files…")
        self._search_edit.setText(self._load_query())
        self._search_edit.textChanged.connect(self._schedule_search)
        self._search_edit.textChanged.connect(self._persist_query)
        self._search_edit.installEventFilter(self)

        self._scope_picker = SearchScopePicker(initial_root, self)
        self._scope_picker.path_changed.connect(self._on_root_changed)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(1)
        self._tree.setHeaderLabels(["Text matches"])
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(max(int(tree_indent_width), 1))
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.installEventFilter(self)

        self._status_label = QLabel(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._search_edit)
        layout.addWidget(self._scope_picker)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._status_label)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(max(int(debounce_ms), 50))
        self._debounce_timer.timeout.connect(self._start_search)
        self._show_idle_state()

    @property
    def search_edit(self) -> QLineEdit:
        """Expose the query editor for window-level focus control."""
        return self._search_edit

    @property
    def root_path(self) -> Path:
        """Return the active recursive text-search root."""
        return self._scope_picker.path

    def set_root_path(self, path: str | Path) -> None:
        """Change the recursive text-search root through the shared picker."""
        self._scope_picker.set_path(path, emit=True)

    def set_session_settings(self, session_settings) -> None:
        """Attach session persistence and restore stored text-search state."""
        self._session_settings = session_settings
        stored_root = self._load_root()
        stored_query = self._load_query()
        self._scope_picker.set_path(stored_root, emit=False)
        if stored_query and not self._search_edit.text():
            self._search_edit.setText(stored_query)

    def apply_settings(
        self,
        default_root_path: str | Path,
        max_results: int,
        debounce_ms: int,
        ignore_file_path: str | Path,
        tree_indent_width: int,
    ) -> None:
        """Apply live search settings without discarding a valid stored scope."""
        self._default_root_path = self._validated_root(default_root_path)
        self._max_results = max(int(max_results), 1)
        self._ignore_file_path = Path(ignore_file_path).expanduser().resolve()
        self._debounce_timer.setInterval(max(int(debounce_ms), 50))
        self._tree.setIndentation(max(int(tree_indent_width), 1))
        if not self._scope_picker.path.is_dir():
            self._scope_picker.set_path(self._default_root_path, emit=True)

    def show_and_focus(self, select_all: bool = True) -> None:
        """Focus the text query and optionally select its complete value."""
        self._search_edit.setFocus()
        if select_all:
            self._search_edit.selectAll()
        if self._search_edit.text().strip():
            self._schedule_search()

    def eventFilter(self, watched, event) -> bool:
        """Handle keyboard navigation and result activation for text search."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if watched is self._search_edit:
                if key == Qt.Key.Key_Down and self._focus_first_result():
                    return True
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                    if not self._activate_current_or_first():
                        self._start_search()
                    return True
            if watched is self._tree and key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                item = self._tree.currentItem()
                if item is not None:
                    self._activate_item(item)
                return True
        return super().eventFilter(watched, event)

    def shutdown(self) -> None:
        """Stop and join text-search workers during application shutdown."""
        self._debounce_timer.stop()
        self._interrupt_threads()
        for thread in list(self._threads):
            if thread.isRunning():
                thread.wait(1500)

    def cancel(self) -> None:
        """Cancel pending text-search work without blocking the GUI thread."""
        self._generation += 1
        self._debounce_timer.stop()
        self._interrupt_threads()

    def _schedule_search(self) -> None:
        """Debounce a non-empty text query before scanning files."""
        query = self._search_edit.text().strip()
        if not query:
            self._show_idle_state()
            return
        self._status_label.setText("Searching file contents…")
        self._debounce_timer.start()

    def _start_search(self) -> None:
        """Start a cancellable background text-search worker."""
        query = self._search_edit.text().strip()
        if not query:
            self._show_idle_state()
            return

        self._generation += 1
        generation = self._generation
        self._interrupt_threads()

        thread = TextFileSearchThread(
            generation=generation,
            root_path=self._scope_picker.path,
            query=query,
            max_results=self._max_results,
            ignore_file_path=self._ignore_file_path,
            parent=self,
        )
        self._threads.append(thread)
        thread.results_ready.connect(self._apply_results)
        thread.finished.connect(lambda item=thread: self._remove_thread(item))
        thread.start()

    def _apply_results(self, generation: int, results: object, truncated: bool) -> None:
        """Render text-search results produced by the current generation."""
        if generation != self._generation:
            return

        file_results = list(results)
        self._populate_tree(file_results)
        occurrence_count = sum(
            len(file_result.get("occurrences", []))
            for file_result in file_results
        )
        if occurrence_count == 0:
            self._status_label.setText("No text matches")
            return

        suffix = " (result limit reached)" if truncated else ""
        self._status_label.setText(
            f"{occurrence_count} occurrence(s) in {len(file_results)} file(s){suffix}"
        )

    def _populate_tree(self, file_results: list[dict]) -> None:
        """Build folder, file, LaTeX-structure, and occurrence result nodes."""
        self._tree.setUpdatesEnabled(False)
        previous = self._tree.blockSignals(True)
        try:
            self._tree.clear()
            root_path = self._scope_picker.path
            root_item = QTreeWidgetItem([root_path.name or str(root_path)])
            root_item.setToolTip(0, str(root_path))
            root_item.setIcon(
                0,
                self._tree.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon),
            )
            self._tree.addTopLevelItem(root_item)
            directory_nodes: dict[tuple[str, ...], QTreeWidgetItem] = {(): root_item}

            for file_result in file_results:
                path_text = str(file_result["path"])
                relative = Path(str(file_result["relative_path"]))
                parent = root_item
                directory_key: tuple[str, ...] = ()

                for part in relative.parts[:-1]:
                    directory_key = directory_key + (part,)
                    directory_item = directory_nodes.get(directory_key)
                    if directory_item is None:
                        directory_item = QTreeWidgetItem([part])
                        directory_item.setIcon(
                            0,
                            self._tree.style().standardIcon(
                                QStyle.StandardPixmap.SP_DirIcon
                            ),
                        )
                        parent.addChild(directory_item)
                        directory_nodes[directory_key] = directory_item
                    parent = directory_item

                file_item = QTreeWidgetItem([relative.name])
                file_item.setToolTip(0, path_text)
                file_item.setIcon(
                    0,
                    self._tree.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
                )
                parent.addChild(file_item)
                structure_nodes: dict[tuple, QTreeWidgetItem] = {}

                for occurrence in file_result["occurrences"]:
                    occurrence_parent = file_item
                    structure_key: tuple = ()
                    for kind, title, heading_line in occurrence.get("structure", ()):
                        structure_key = structure_key + ((kind, title, heading_line),)
                        structure_item = structure_nodes.get(structure_key)
                        if structure_item is None:
                            structure_item = QTreeWidgetItem([f"{kind}: {title}"])
                            occurrence_parent.addChild(structure_item)
                            structure_nodes[structure_key] = structure_item
                        occurrence_parent = structure_item

                    snippet = occurrence.get("snippet", "")
                    line = int(occurrence["line"])
                    column = int(occurrence["column"])
                    label = f"Line {line}, Col {column}: {snippet}"
                    match_item = QTreeWidgetItem([label])
                    match_item.setData(
                        0,
                        self._LOCATION_ROLE,
                        (path_text, line, column),
                    )
                    match_item.setData(0, self._HIT_ROLE, True)
                    font = match_item.font(0)
                    font.setBold(True)
                    match_item.setFont(0, font)
                    occurrence_parent.addChild(match_item)

                file_item.setExpanded(True)
                for structure_item in structure_nodes.values():
                    structure_item.setExpanded(True)

            root_item.setExpanded(True)
            for directory_item in directory_nodes.values():
                directory_item.setExpanded(True)
        finally:
            self._tree.blockSignals(previous)
            self._tree.setUpdatesEnabled(True)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Activate a double-clicked text-search result."""
        del column
        self._activate_item(item)

    def _activate_item(self, item: QTreeWidgetItem) -> bool:
        """Open a concrete occurrence or toggle a grouping node."""
        location = item.data(0, self._LOCATION_ROLE)
        if not location:
            item.setExpanded(not item.isExpanded())
            return False
        path_text, line, column = location
        self.location_selected.emit(str(path_text), int(line), int(column))
        return True

    def _activate_current_or_first(self) -> bool:
        """Activate the selected occurrence or the first available hit."""
        item = self._tree.currentItem()
        if item is None or not bool(item.data(0, self._HIT_ROLE)):
            if not self._focus_first_result():
                return False
            item = self._tree.currentItem()
        return bool(item is not None and self._activate_item(item))

    def _focus_first_result(self) -> bool:
        """Move keyboard focus to the first concrete text occurrence."""
        def walk(parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
            """Return the first concrete occurrence below a tree node."""
            for index in range(parent.childCount()):
                child = parent.child(index)
                if bool(child.data(0, self._HIT_ROLE)):
                    return child
                nested = walk(child)
                if nested is not None:
                    return nested
            return None

        item = walk(self._tree.invisibleRootItem())
        if item is None:
            return False
        self._tree.setCurrentItem(item)
        self._tree.scrollToItem(
            item,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self._tree.setFocus()
        return True

    def _on_root_changed(self, path_text: str) -> None:
        """Persist a new root and refresh the current text query."""
        self._persist_root(path_text)
        if self._search_edit.text().strip():
            self._schedule_search()
        else:
            self._show_idle_state()

    def _show_idle_state(self) -> None:
        """Clear results and show the idle text-search status."""
        self._generation += 1
        self._debounce_timer.stop()
        self._interrupt_threads()
        self._tree.clear()
        self._status_label.setText("Type text to search recursively in files")

    def _interrupt_threads(self) -> None:
        """Request cooperative cancellation of active text workers."""
        for thread in list(self._threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _remove_thread(self, thread: TextFileSearchThread) -> None:
        """Release a completed text-search worker."""
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _persist_query(self, text: str) -> None:
        """Persist the current text-search query in the session."""
        if self._session_settings is not None:
            self._session_settings.setValue(self._SESSION_QUERY_KEY, str(text))

    def _persist_root(self, path_text: str) -> None:
        """Persist the current text-search root in the session."""
        if self._session_settings is not None:
            self._session_settings.setValue(self._SESSION_ROOT_KEY, str(path_text))

    def _load_query(self) -> str:
        """Load the last persisted text-search query."""
        if self._session_settings is None:
            return ""
        return str(self._session_settings.value(self._SESSION_QUERY_KEY, "") or "")

    def _load_root(self) -> Path:
        """Load a valid persisted text-search root or the configured default."""
        if self._session_settings is None:
            return self._default_root_path
        stored = self._session_settings.value(
            self._SESSION_ROOT_KEY,
            str(self._default_root_path),
        )
        candidate = Path(str(stored)).expanduser()
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            pass
        return self._default_root_path

    @staticmethod
    def _validated_root(path: str | Path) -> Path:
        """Return a resolved directory suitable as a text-search root."""
        candidate = Path(path).expanduser()
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            pass
        return Path.home().resolve()
