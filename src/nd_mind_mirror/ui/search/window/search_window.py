"""Responsive Double-Shift file and folder search window."""

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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.ui.search.search_typing_controller import (
    SearchTypingController,
)
from nd_mind_mirror.ui.search.thread.cooperative_file_search_index_thread import (
    CooperativeFileSearchIndexThread,
)
from nd_mind_mirror.ui.search.thread.cooperative_file_search_thread import (
    CooperativeFileSearchThread,
)
from nd_mind_mirror.ui.search.window.search_result_tree_presenter import (
    SearchResultTreePresenter,
)


class SearchWindow(QWidget):
    """Search the configured workspace without ever blocking the input field."""

    latex_file_selected = Signal(str)

    _HIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    _DIRECTORY_ROLE = int(Qt.ItemDataRole.UserRole) + 2

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
        super().__init__(
            parent,
            Qt.WindowType.Window,
        )

        self.setWindowTitle(
            "Search Files and Folders"
        )

        self._root_path = self._validated_root(
            root_path
        )
        self._max_results = max(
            int(max_results),
            1,
        )
        self._ignore_file_path = Path(
            ignore_file_path
        ).expanduser().resolve()
        self._fuzzy_threshold = float(
            fuzzy_threshold
        )
        self._hierarchical_path_matching = bool(
            hierarchical_path_matching
        )
        self._window_width = max(
            int(window_width),
            420,
        )
        self._window_height = max(
            int(window_height),
            320,
        )

        self._generation = 0
        self._index_generation = 0
        self._threads: list[
            CooperativeFileSearchThread
        ] = []
        self._index_threads: list[
            CooperativeFileSearchIndexThread
        ] = []
        # Compatibility boundary for the legacy large-document controller.
        # Its historical runtime hook still writes ``_index_thread`` directly.
        # The property below tracks that worker in the canonical thread list so
        # cancellation and shutdown remain safe until that old hook is removed.
        self._legacy_index_thread = None
        self._search_index: list[
            tuple[str, str, str, str, str, bool, str]
        ] = []
        self._directory_flags: dict[str, bool] = {}
        self._index_ready = False
        self._shutdown_started = False

        self._path_label = QLabel(self)
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText(
            "Type part of a file/folder name; small spelling mistakes are tolerated..."
        )
        self._search_edit.textChanged.connect(
            self._schedule_search
        )
        self._search_edit.installEventFilter(self)

        self._close_button = QPushButton(
            "Close",
            self,
        )
        self._close_button.clicked.connect(
            self.close
        )

        top_layout = QHBoxLayout()
        top_layout.addWidget(
            self._search_edit,
            1,
        )
        top_layout.addWidget(
            self._close_button,
        )

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(1)
        self._tree.setHeaderLabels(["Name"])
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(
            max(
                int(tree_indent_width),
                1,
            )
        )
        self._tree.itemDoubleClicked.connect(
            self._on_item_double_clicked
        )
        self._tree.installEventFilter(self)

        self._result_presenter = SearchResultTreePresenter(
            tree=self._tree,
            hit_role=self._HIT_ROLE,
            directory_role=self._DIRECTORY_ROLE,
        )

        self._status_label = QLabel(self)

        layout = QVBoxLayout(self)
        layout.addWidget(
            self._path_label
        )
        layout.addLayout(
            top_layout
        )
        layout.addWidget(
            self._tree,
            1,
        )
        layout.addWidget(
            self._status_label
        )

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(
            max(
                int(debounce_ms),
                50,
            )
        )
        self._debounce_timer.timeout.connect(
            self._start_search
        )

        self._typing_controller = SearchTypingController(
            self,
            self,
        )

        application = QApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(
                self.shutdown
            )

        self._refresh_root_label()
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
        """Open Search, or just refocus it if Double Shift fires again."""
        was_visible = self.isVisible()

        if not was_visible:
            if not self._has_running_index_thread():
                self.rebuild_index()

            self._center_on_parent()
            self.show()
            self._center_on_parent()

        self.raise_()
        self.activateWindow()
        self._search_edit.setFocus()

        if was_visible:
            return

        # Preserve the previous query but let the next typed character replace it.
        self._search_edit.selectAll()

        if self._search_edit.text().strip():
            self._schedule_search()

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
        self._root_path = self._validated_root(
            root_path
        )
        self._max_results = max(
            int(max_results),
            1,
        )
        self._ignore_file_path = Path(
            ignore_file_path
        ).expanduser().resolve()
        self._fuzzy_threshold = float(
            fuzzy_threshold
        )
        self._hierarchical_path_matching = bool(
            hierarchical_path_matching
        )
        self._window_width = max(
            int(window_width),
            420,
        )
        self._window_height = max(
            int(window_height),
            320,
        )
        self._tree.setIndentation(
            max(
                int(tree_indent_width),
                1,
            )
        )
        self._debounce_timer.setInterval(
            max(
                int(debounce_ms),
                50,
            )
        )
        self._typing_controller.apply()
        self._refresh_root_label()
        self.rebuild_index()

    def rebuild_index(self) -> None:
        """Refresh names in the background while keeping the last good index usable."""
        self._index_generation += 1
        generation = self._index_generation
        had_index = self._index_ready

        self._generation += 1
        self._debounce_timer.stop()
        self._interrupt_search_threads()
        self._interrupt_index_threads()

        if not had_index:
            self._index_ready = False

        self._status_label.setText(
            "Refreshing search index..."
            if had_index
            else "Indexing search root..."
        )

        thread = CooperativeFileSearchIndexThread(
            generation=generation,
            root_path=self._root_path,
            ignore_file_path=self._ignore_file_path,
            parent=self,
        )
        self._index_threads.append(thread)
        thread.index_ready.connect(
            self._apply_index
        )
        thread.finished.connect(
            lambda item=thread:
            self._remove_index_thread(item)
        )
        thread.start()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()

            if watched is self._search_edit:
                if key == Qt.Key.Key_Down:
                    if self._focus_first_search_result():
                        return True

                if key in {
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                }:
                    item = self._tree.currentItem()
                    if (
                        item is None
                        or not bool(
                            item.data(
                                0,
                                self._HIT_ROLE,
                            )
                        )
                    ):
                        self._focus_first_search_result()
                        item = self._tree.currentItem()

                    if item is not None:
                        self._activate_item(item)
                    return True

            if watched is self._tree:
                if key in {
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                }:
                    item = self._tree.currentItem()
                    if item is not None:
                        self._activate_item(item)
                    return True

        return super().eventFilter(
            watched,
            event,
        )

    def keyPressEvent(
        self,
        event: QKeyEvent,
    ) -> None:
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
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Join workers only when the application itself is exiting."""
        if self._shutdown_started:
            return

        self._shutdown_started = True
        self._debounce_timer.stop()
        self._interrupt_search_threads()
        self._interrupt_index_threads()

        for thread in list(self._threads):
            if thread.isRunning():
                thread.wait(1500)

        for thread in list(self._index_threads):
            if thread.isRunning():
                thread.wait(1500)

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()

        if parent is None:
            self.resize(
                self._window_width,
                self._window_height,
            )
            return

        parent_geometry = parent.frameGeometry()

        width = min(
            self._window_width,
            max(
                parent_geometry.width() - 40,
                420,
            ),
        )
        height = min(
            self._window_height,
            max(
                parent_geometry.height() - 60,
                320,
            ),
        )

        self.resize(
            width,
            height,
        )

        frame = self.frameGeometry()
        frame.moveCenter(
            parent_geometry.center()
        )
        self.move(
            frame.topLeft()
        )

    def _schedule_search(self) -> None:
        query = self._search_edit.text().strip()

        if not query:
            self._debounce_timer.stop()
            self._show_idle_state()
            return

        if not self._index_ready:
            self._status_label.setText(
                "Indexing search root..."
            )
            return

        # If the legacy performance controller started a background refresh,
        # user typing has priority.  The last complete index remains valid and
        # searchable while the refresh is cancelled cooperatively.
        legacy_index_thread = self._legacy_index_thread
        if (
            legacy_index_thread is not None
            and legacy_index_thread.isRunning()
        ):
            legacy_index_thread.requestInterruption()

        self._status_label.setText(
            "Searching..."
        )
        self._debounce_timer.start()

    def _start_search(self) -> None:
        query = self._search_edit.text().strip()

        if not query:
            self._show_idle_state()
            return

        if not self._index_ready:
            return

        self._generation += 1
        generation = self._generation
        self._interrupt_search_threads()

        thread = CooperativeFileSearchThread(
            generation=generation,
            entries=self._search_index,
            query=query,
            max_results=self._max_results,
            fuzzy_threshold=self._fuzzy_threshold,
            hierarchical_path_matching=(
                self._hierarchical_path_matching
            ),
            parent=self,
        )
        self._threads.append(thread)
        thread.results_ready.connect(
            self._apply_results
        )
        thread.finished.connect(
            lambda item=thread:
            self._remove_thread(item)
        )
        thread.start()

    def _apply_index(
        self,
        generation: int,
        entries: object,
    ) -> None:
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

    def _apply_results(
        self,
        generation: int,
        results: object,
        truncated: bool,
    ) -> None:
        if generation != self._generation:
            return

        paths = [
            Path(value)
            for value in results
        ]

        self._result_presenter.populate(
            root_path=self._root_path,
            paths=paths,
            directory_flags=self._directory_flags,
        )

        if not paths:
            self._status_label.setText(
                "No matches"
            )
            return

        suffix = (
            " (result limit reached)"
            if truncated
            else ""
        )
        self._status_label.setText(
            f"{len(paths)} matches{suffix}"
        )

    def _on_item_double_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        self._activate_item(item)

    def _activate_item(
        self,
        item: QTreeWidgetItem,
    ) -> None:
        path_text = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )
        if not path_text:
            return

        path_text = str(path_text)
        is_directory = bool(
            item.data(
                0,
                self._DIRECTORY_ROLE,
            )
        )

        if is_directory:
            parent = self.parentWidget()
            navigator = getattr(
                parent,
                "_file_system_panel",
                None,
            )
            if navigator is not None:
                navigator.select_path(
                    path_text,
                    force_reveal=True,
                )
            self.close()
            return

        self.latex_file_selected.emit(
            path_text
        )
        self.close()

    def _focus_first_search_result(self) -> bool:
        iterator = self._tree.invisibleRootItem()

        def walk(
            parent: QTreeWidgetItem,
        ) -> QTreeWidgetItem | None:
            for index in range(
                parent.childCount()
            ):
                child = parent.child(index)
                if bool(
                    child.data(
                        0,
                        self._HIT_ROLE,
                    )
                ):
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
        self._generation += 1
        self._tree.clear()

        if self._index_ready:
            self._status_label.setText(
                "Type a partial name to search"
            )
        else:
            self._status_label.setText(
                "Indexing search root..."
            )

    def _validated_root(
        self,
        root_path: str | Path,
    ) -> Path:
        candidate = Path(
            root_path
        ).expanduser()

        if candidate.is_dir():
            return candidate.resolve()

        return Path.home().resolve()

    def _refresh_root_label(self) -> None:
        self._path_label.setText(
            f"Search root: {self._root_path}"
        )

    def _interrupt_search_threads(self) -> None:
        for thread in list(self._threads):
            if thread.isRunning():
                thread.requestInterruption()

    def _interrupt_index_threads(self) -> None:
        for thread in list(
            self._index_threads
        ):
            if thread.isRunning():
                thread.requestInterruption()

    def _has_running_index_thread(self) -> bool:
        return any(
            thread.isRunning()
            for thread in self._index_threads
        )

    def _remove_thread(
        self,
        thread: CooperativeFileSearchThread,
    ) -> None:
        if thread in self._threads:
            self._threads.remove(thread)

        thread.deleteLater()

    def _remove_index_thread(
        self,
        thread,
    ) -> None:
        if thread in self._index_threads:
            self._index_threads.remove(thread)

        if self._legacy_index_thread is thread:
            self._legacy_index_thread = None

        thread.deleteLater()
