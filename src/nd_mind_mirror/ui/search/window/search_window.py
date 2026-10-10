"""Two-mode responsive workspace search window."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.ui.search.search_typing_controller import SearchTypingController
from nd_mind_mirror.ui.search.thread.cooperative_file_search_index_thread import (
    CooperativeFileSearchIndexThread,
)
from nd_mind_mirror.ui.search.thread.cooperative_file_search_thread import (
    CooperativeFileSearchThread,
)
from nd_mind_mirror.ui.search.window.search_result_tree_presenter import (
    SearchResultTreePresenter,
)
from nd_mind_mirror.ui.search.window.search_scope_picker import SearchScopePicker
from nd_mind_mirror.ui.search.window.text_search_tab import TextSearchTab


class SearchWindow(QWidget):
    """Search names or file contents without blocking editor input."""

    latex_file_selected = Signal(str)
    text_location_selected = Signal(str, int, int)

    _HIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    _DIRECTORY_ROLE = int(Qt.ItemDataRole.UserRole) + 2
    _SESSION_FILE_QUERY_KEY = "search/files/query"
    _SESSION_FILE_ROOT_KEY = "search/files/root_path"

    def __init__(
        self,
        root_path: str | Path,
        max_results: int,
        debounce_ms: int,
        ignore_file_path: str | Path,
        fuzzy_threshold: float,
        window_width: int,
        window_height: int,
        tree_indent_width: int,
        hierarchical_path_matching: bool = True,
        parent=None,
    ) -> None:
        """Initialize the two-tab workspace search window."""
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Search")

        self._default_root_path = self._validated_root(root_path)
        self._session_settings = getattr(parent, "_session_settings", None)
        self._root_path = self._load_file_root()
        self._max_results = max(int(max_results), 1)
        self._ignore_file_path = Path(ignore_file_path).expanduser().resolve()
        self._fuzzy_threshold = float(fuzzy_threshold)
        self._hierarchical_path_matching = bool(hierarchical_path_matching)
        self._window_width = max(int(window_width), 520)
        self._window_height = max(int(window_height), 420)
        self._tree_indent_width = max(int(tree_indent_width), 1)

        self._generation = 0
        self._index_generation = 0
        self._threads: list[CooperativeFileSearchThread] = []
        self._index_threads: list[CooperativeFileSearchIndexThread] = []
        self._legacy_index_thread = None
        self._search_index: list[
            tuple[str, str, str, str, str, bool, str]
        ] = []
        self._directory_flags: dict[str, bool] = {}
        self._index_ready = False
        self._shutdown_started = False
        self._active_query: str | None = None
        self._displayed_query: str | None = None
        self._displayed_index_generation = -1

        self._tabs = QTabWidget(self)
        self._file_tab = self._build_file_search_tab(debounce_ms)
        self._tabs.addTab(self._file_tab, "Files & Folders")

        self._text_search_tab = TextSearchTab(
            default_root_path=self._default_root_path,
            max_results=self._max_results,
            debounce_ms=debounce_ms,
            ignore_file_path=self._ignore_file_path,
            tree_indent_width=self._tree_indent_width,
            session_settings=self._session_settings,
            parent=self,
        )
        self._text_search_tab.location_selected.connect(
            self._forward_text_location
        )
        self._tabs.addTab(self._text_search_tab, "Text in Files")

        self._close_button = QPushButton("Close", self)
        self._close_button.clicked.connect(self.close)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self._close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs, 1)
        layout.addLayout(bottom_layout)

        self._typing_controller = SearchTypingController(self, self)

        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

        self._show_idle_state()
        self.rebuild_index()

    @property
    def _index_thread(self):
        """Expose the historical single-index-thread name without splitting ownership."""
        return self._legacy_index_thread

    @_index_thread.setter
    def _index_thread(self, thread) -> None:
        """Track legacy-assigned index workers in the canonical lifecycle list."""
        self._legacy_index_thread = thread
        if thread is not None and thread not in self._index_threads:
            self._index_threads.append(thread)

    def show_and_focus(self) -> None:
        """Double Shift always opens the Files & Folders tab."""
        self._tabs.setCurrentWidget(self._file_tab)
        was_visible = self.isVisible()

        if not was_visible:
            if not self._index_ready and not self._has_running_index_thread():
                self.rebuild_index()
            self._center_on_parent()
            self.show()
            self._center_on_parent()

        self.raise_()
        self.activateWindow()
        self._search_edit.setFocus()

        if was_visible:
            return

        self._search_edit.selectAll()
        if self._search_edit.text().strip():
            self._schedule_search()

    def show_file_search(self, root_path: str | Path | None = None) -> None:
        """Open the file/folder tab and optionally scope it to a Navigator folder."""
        was_visible = self.isVisible()
        if root_path is not None:
            previous_root = self._root_path
            self._file_scope_picker.set_path(root_path, emit=True)
            if (
                not was_visible
                and self._root_path == previous_root
                and not self._index_ready
                and not self._has_running_index_thread()
            ):
                self.rebuild_index()
        elif (
            not was_visible
            and not self._index_ready
            and not self._has_running_index_thread()
        ):
            self.rebuild_index()
        self._tabs.setCurrentWidget(self._file_tab)
        self._show_window()
        self._search_edit.setFocus()
        self._search_edit.selectAll()
        if self._search_edit.text().strip():
            self._schedule_search()

    def show_text_search(self, root_path: str | Path | None = None) -> None:
        """Open text search and optionally scope it to a Navigator folder."""
        if root_path is not None:
            self._text_search_tab.set_root_path(root_path)
        self._tabs.setCurrentWidget(self._text_search_tab)
        self._show_window()
        self._text_search_tab.show_and_focus(select_all=True)

    def set_session_settings(self, session_settings) -> None:
        """Attach persistent session settings when a higher window layer owns them."""
        self._session_settings = session_settings
        stored_root = self._load_file_root()
        stored_query = self._load_file_query()
        root_changed = stored_root != self._root_path
        self._root_path = stored_root
        self._file_scope_picker.set_path(stored_root, emit=False)
        if stored_query and not self._search_edit.text():
            self._search_edit.setText(stored_query)
        self._text_search_tab.set_session_settings(session_settings)
        if root_changed:
            self.rebuild_index()

    def apply_settings(
        self,
        root_path: str | Path,
        max_results: int,
        debounce_ms: int,
        ignore_file_path: str | Path,
        fuzzy_threshold: float,
        window_width: int,
        window_height: int,
        tree_indent_width: int,
        hierarchical_path_matching: bool = True,
    ) -> None:
        """Apply live workspace-search settings while preserving valid scopes."""
        self._default_root_path = self._validated_root(root_path)
        self._max_results = max(int(max_results), 1)
        self._ignore_file_path = Path(ignore_file_path).expanduser().resolve()
        self._fuzzy_threshold = float(fuzzy_threshold)
        self._hierarchical_path_matching = bool(hierarchical_path_matching)
        self._window_width = max(int(window_width), 520)
        self._window_height = max(int(window_height), 420)
        self._tree_indent_width = max(int(tree_indent_width), 1)
        self._tree.setIndentation(self._tree_indent_width)
        self._debounce_timer.setInterval(max(int(debounce_ms), 50))
        self._typing_controller.apply()

        if not self._root_path.is_dir():
            self._set_file_root(self._default_root_path, persist=True)
        else:
            self.rebuild_index()

        self._text_search_tab.apply_settings(
            default_root_path=self._default_root_path,
            max_results=self._max_results,
            debounce_ms=debounce_ms,
            ignore_file_path=self._ignore_file_path,
            tree_indent_width=self._tree_indent_width,
        )

    def rebuild_index(self) -> None:
        """Refresh names in the background while keeping the last good index usable."""
        self._index_generation += 1
        generation = self._index_generation
        had_index = self._index_ready

        self._generation += 1
        self._displayed_index_generation = -1
        self._debounce_timer.stop()
        self._interrupt_search_threads()
        self._interrupt_index_threads()

        if not had_index:
            self._index_ready = False

        self._status_label.setText(
            "Refreshing search index..." if had_index else "Indexing search root..."
        )

        thread = CooperativeFileSearchIndexThread(
            generation=generation,
            root_path=self._root_path,
            ignore_file_path=self._ignore_file_path,
            parent=self,
        )
        self._index_threads.append(thread)
        thread.index_ready.connect(self._apply_index)
        thread.finished.connect(lambda item=thread: self._remove_index_thread(item))
        thread.start()

    def eventFilter(self, watched, event) -> bool:
        """Handle keyboard navigation and activation in file search."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if watched is self._search_edit:
                if key == Qt.Key.Key_Down:
                    if self._focus_first_search_result():
                        return True
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                    item = self._tree.currentItem()
                    if item is None or not bool(item.data(0, self._HIT_ROLE)):
                        self._focus_first_search_result()
                        item = self._tree.currentItem()
                    if item is not None:
                        self._activate_item(item)
                    return True

            if watched is self._tree and key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                item = self._tree.currentItem()
                if item is not None:
                    self._activate_item(item)
                return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Close the search window when Escape is pressed."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Hide promptly; workers stop cooperatively without GUI-thread waits."""
        self._generation += 1
        self._debounce_timer.stop()
        self._interrupt_search_threads()
        self._interrupt_index_threads()
        self._text_search_tab.cancel()
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Join workers only when the application itself is exiting."""
        if self._shutdown_started:
            return
        self._shutdown_started = True
        self._debounce_timer.stop()
        self._interrupt_search_threads()
        self._interrupt_index_threads()
        self._text_search_tab.shutdown()

        for thread in list(self._threads):
            if thread.isRunning():
                thread.wait(1500)
        for thread in list(self._index_threads):
            if thread.isRunning():
                thread.wait(1500)

    def _build_file_search_tab(self, debounce_ms: int) -> QWidget:
        """Construct the file/folder search tab and its worker timer."""
        tab = QWidget(self)

        self._search_edit = QLineEdit(tab)
        self._search_edit.setPlaceholderText(
            "Search file/folder names or paste a full file path..."
        )
        self._search_edit.setText(self._load_file_query())
        self._search_edit.textChanged.connect(self._schedule_search)
        self._search_edit.textChanged.connect(self._persist_file_query)
        self._search_edit.installEventFilter(self)

        self._file_scope_picker = SearchScopePicker(self._root_path, tab)
        self._file_scope_picker.path_changed.connect(self._on_file_root_changed)

        self._tree = QTreeWidget(tab)
        self._tree.setColumnCount(1)
        self._tree.setHeaderLabels(["Name"])
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(self._tree_indent_width)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.installEventFilter(self)

        self._result_presenter = SearchResultTreePresenter(
            tree=self._tree,
            hit_role=self._HIT_ROLE,
            directory_role=self._DIRECTORY_ROLE,
        )
        self._status_label = QLabel(tab)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self._refresh_button = QPushButton("Refresh index", tab)
        self._refresh_button.setToolTip("Rescan folders for external file changes")
        self._refresh_button.clicked.connect(self.rebuild_index)
        scope_layout = QHBoxLayout()
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.addWidget(self._file_scope_picker, 1)
        scope_layout.addWidget(self._refresh_button)

        layout.addWidget(self._search_edit)
        layout.addLayout(scope_layout)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._status_label)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(max(int(debounce_ms), 50))
        self._debounce_timer.timeout.connect(self._start_search)
        return tab

    def _show_window(self) -> None:
        """Show, raise, and activate the search window."""
        if not self.isVisible():
            self._center_on_parent()
            self.show()
            self._center_on_parent()
        self.raise_()
        self.activateWindow()

    def _center_on_parent(self) -> None:
        """Size and center the search window over its parent."""
        parent = self.parentWidget()
        if parent is None:
            self.resize(self._window_width, self._window_height)
            return

        parent_geometry = parent.frameGeometry()
        width = min(
            self._window_width,
            max(parent_geometry.width() - 40, 520),
        )
        height = min(
            self._window_height,
            max(parent_geometry.height() - 60, 420),
        )
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(parent_geometry.center())
        self.move(frame.topLeft())

    def _schedule_search(self) -> None:
        """Debounce changed queries while reusing already displayed valid results."""
        query = self._search_edit.text().strip()
        if not query:
            self._debounce_timer.stop()
            self._show_idle_state()
            return
        if (
            query == self._displayed_query
            and self._displayed_index_generation == self._index_generation
        ):
            self._debounce_timer.stop()
            return
        if not self._index_ready and "/" not in query:
            self._status_label.setText("Indexing search root...")
            return

        legacy_index_thread = self._legacy_index_thread
        if legacy_index_thread is not None and legacy_index_thread.isRunning():
            legacy_index_thread.requestInterruption()

        self._generation += 1
        self._interrupt_search_threads()
        self._status_label.setText("Searching...")
        self._debounce_timer.start()

    def _start_search(self) -> None:
        """Start a cancellable search; explicit full paths work before indexing."""
        query = self._search_edit.text().strip()
        if not query:
            self._show_idle_state()
            return
        if not self._index_ready and "/" not in query:
            return

        self._generation += 1
        generation = self._generation
        self._active_query = query
        self._interrupt_search_threads()

        thread = CooperativeFileSearchThread(
            generation=generation,
            entries=self._search_index,
            query=query,
            max_results=self._max_results,
            fuzzy_threshold=self._fuzzy_threshold,
            hierarchical_path_matching=self._hierarchical_path_matching,
            parent=self,
            root_path=self._root_path,
            workspace_root_path=self._default_root_path,
        )
        self._threads.append(thread)
        thread.results_ready.connect(self._apply_results)
        thread.finished.connect(lambda item=thread: self._remove_thread(item))
        thread.start()

    def _apply_index(self, generation: int, entries: object) -> None:
        """Accept the newest completed file-search index."""
        if generation != self._index_generation:
            return

        indexed_entries = list(entries)
        self._search_index = indexed_entries
        self._directory_flags = {
            str(path_text): bool(is_directory)
            for (
                path_text,
                _name_text,
                _stem_text,
                _normalized_name,
                _normalized_stem,
                is_directory,
                _relative_path,
            ) in indexed_entries
        }
        self._index_ready = True

        query = self._search_edit.text().strip()
        if query:
            self._schedule_search()
            return
        self._status_label.setText(
            f"Indexed {len(self._search_index)} files and folders"
        )

    def _apply_results(self, generation: int, results: object, truncated: bool) -> None:
        """Render the newest file/folder search results."""
        if (
            generation != self._generation
            or self._active_query != self._search_edit.text().strip()
        ):
            return

        paths = [
            Path(value["path"] if isinstance(value, dict) else value)
            for value in results
        ]
        directory_flags = self._directory_flags
        if any(isinstance(value, dict) for value in results):
            directory_flags = self._directory_flags.copy()
            for value in results:
                if isinstance(value, dict):
                    directory_flags[str(value["path"])] = bool(value["is_directory"])
        display_root = self._root_path
        if paths and any(not path.is_relative_to(display_root) for path in paths):
            display_root = paths[0].parent
        self._result_presenter.populate(
            root_path=display_root,
            paths=paths,
            directory_flags=directory_flags,
        )
        self._displayed_query = self._active_query
        self._displayed_index_generation = self._index_generation
        if not paths:
            self._status_label.setText("No matches")
            return

        suffix = " (result limit reached)" if truncated else ""
        self._status_label.setText(f"{len(paths)} matches{suffix}")

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Activate a double-clicked file/folder result."""
        del column
        self._activate_item(item)

    def _activate_item(self, item: QTreeWidgetItem) -> None:
        """Open a file hit or reveal a folder hit in Navigator."""
        path_text = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_text:
            return
        path_text = str(path_text)
        is_directory = bool(item.data(0, self._DIRECTORY_ROLE))

        if is_directory:
            parent = self.parentWidget()
            navigator = getattr(parent, "_file_system_panel", None)
            if navigator is not None:
                navigator.select_path(path_text, force_reveal=True)
            self.close()
            return

        self.latex_file_selected.emit(path_text)
        self.close()

    def _focus_first_search_result(self) -> bool:
        """Move keyboard focus to the first concrete file/folder hit."""
        iterator = self._tree.invisibleRootItem()

        def walk(parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
            """Return the first concrete file/folder hit below a tree node."""
            for index in range(parent.childCount()):
                child = parent.child(index)
                if bool(child.data(0, self._HIT_ROLE)):
                    return child
                nested = walk(child)
                if nested is not None:
                    return nested
            return None

        item = walk(iterator)
        if item is None:
            return False
        self._tree.setCurrentItem(item)
        self._tree.scrollToItem(
            item,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )
        self._tree.setFocus()
        return True

    def _show_idle_state(self) -> None:
        """Clear file results and display index readiness."""
        self._generation += 1
        self._displayed_query = None
        self._tree.clear()
        if self._index_ready:
            self._status_label.setText(
                f"Indexed {len(self._search_index)} files and folders"
            )
        else:
            self._status_label.setText("Indexing search root...")

    def _on_file_root_changed(self, path_text: str) -> None:
        """Apply a folder-picker change to file/folder search."""
        self._set_file_root(path_text, persist=True)

    def _set_file_root(self, root_path: str | Path, persist: bool) -> None:
        """Persist and rebuild the file-search index for a new root."""
        validated = self._validated_root(root_path)
        if persist:
            self._persist_file_root(str(validated))
        if validated == self._root_path:
            return
        self._root_path = validated
        self._file_scope_picker.set_path(validated, emit=False)
        self._search_index = []
        self._directory_flags = {}
        self._index_ready = False
        self._displayed_query = None
        self.rebuild_index()

    def _forward_text_location(self, path_text: str, line: int, column: int) -> None:
        """Forward a text occurrence and close the shared search window."""
        self.text_location_selected.emit(path_text, line, column)
        self.close()

    def _persist_file_query(self, text: str) -> None:
        """Persist the current file/folder query."""
        if self._session_settings is not None:
            self._session_settings.setValue(self._SESSION_FILE_QUERY_KEY, str(text))

    def _persist_file_root(self, path_text: str) -> None:
        """Persist the current file/folder search root."""
        if self._session_settings is not None:
            self._session_settings.setValue(self._SESSION_FILE_ROOT_KEY, str(path_text))

    def _load_file_query(self) -> str:
        """Load the last file/folder search query."""
        if self._session_settings is None:
            return ""
        return str(self._session_settings.value(self._SESSION_FILE_QUERY_KEY, "") or "")

    def _load_file_root(self) -> Path:
        """Load a valid persisted file-search root or the configured default."""
        if self._session_settings is None:
            return self._default_root_path
        stored = self._session_settings.value(
            self._SESSION_FILE_ROOT_KEY,
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
    def _validated_root(root_path: str | Path) -> Path:
        """Return a resolved directory suitable as a search root."""
        candidate = Path(root_path).expanduser()
        try:
            if candidate.is_dir():
                return candidate.resolve()
        except OSError:
            pass
        return Path.home().resolve()

    def _interrupt_search_threads(self) -> None:
        """Request cancellation of active file-search workers."""
        for thread in list(self._threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _interrupt_index_threads(self) -> None:
        """Request cancellation of active indexing workers."""
        for thread in list(self._index_threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _has_running_index_thread(self) -> bool:
        """Return whether a file-index worker is still running."""
        return any(thread.isRunning() for thread in self._index_threads)

    def _remove_thread(self, thread: CooperativeFileSearchThread) -> None:
        """Release a completed file-search worker."""
        if thread in self._threads:
            self._threads.remove(thread)
        thread.deleteLater()

    def _remove_index_thread(self, thread) -> None:
        """Release a completed file-index worker."""
        if thread in self._index_threads:
            self._index_threads.remove(thread)
        if thread is self._legacy_index_thread:
            self._legacy_index_thread = None
        thread.deleteLater()
