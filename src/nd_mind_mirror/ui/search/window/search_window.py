from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.ui.search.thread.file_search_index_thread import (
    FileSearchIndexThread,
)
from nd_mind_mirror.ui.search.thread.file_search_thread import (
    FileSearchThread,
)


class SearchWindow(QWidget):
    latex_file_selected = Signal(str)
    _HIT_ROLE = int(Qt.ItemDataRole.UserRole) + 1

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
        self._threads: list[
            FileSearchThread
        ] = []
        self._index_generation = 0
        self._index_thread: FileSearchIndexThread | None = None
        self._search_index: list[
            tuple[str, str, str, str, str, bool, str]
        ] = []
        self._index_ready = False

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

        self._refresh_root_label()
        self._show_idle_state()
        self.rebuild_index()

    def show_and_focus(self) -> None:
        was_visible = self.isVisible()

        # The workspace may be changed by Dropbox, git, a terminal, or another
        # editor while Mind Mirror is running. Rebuild the lightweight name
        # index whenever Double Shift opens search so newly created/moved
        # files and folders are searchable immediately without restarting.
        self.rebuild_index()

        self._center_on_parent()
        self.show()
        self._center_on_parent()
        self.raise_()
        self.activateWindow()
        self._search_edit.setFocus()

        # Keep the previous query between invocations, but select it all so the
        # next typed character or Backspace replaces the complete previous
        # query immediately.  Arrow keys can still move the caret normally.
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
        new_root = self._validated_root(
            root_path
        )
        new_ignore_file = Path(
            ignore_file_path
        ).expanduser().resolve()
        self._root_path = new_root
        self._max_results = max(
            int(max_results),
            1,
        )
        self._ignore_file_path = new_ignore_file
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
        self._refresh_root_label()

        # Reloading settings also reloads search_ignore.yaml even when
        # its path did not change.
        self.rebuild_index()

    def rebuild_index(self) -> None:
        self._index_generation += 1
        generation = self._index_generation
        self._index_ready = False
        self._search_index = []
        self._generation += 1
        self._debounce_timer.stop()

        for thread in list(self._threads):
            if thread.isRunning():
                thread.requestInterruption()

        if (
            self._index_thread is not None
            and self._index_thread.isRunning()
        ):
            self._index_thread.requestInterruption()
            self._index_thread.wait(1000)

        self._status_label.setText(
            "Indexing search root..."
        )

        thread = FileSearchIndexThread(
            generation=generation,
            root_path=self._root_path,
            ignore_file_path=self._ignore_file_path,
            parent=self,
        )
        self._index_thread = thread
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
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                    item = self._tree.currentItem()
                    if item is None or not bool(
                        item.data(0, self._HIT_ROLE)
                    ):
                        self._focus_first_search_result()
                        item = self._tree.currentItem()
                    if item is not None:
                        self._activate_item(item)
                    return True

            if watched is self._tree:
                if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                    item = self._tree.currentItem()
                    if item is not None:
                        self._activate_item(item)
                    return True

        return super().eventFilter(watched, event)

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
        self._debounce_timer.stop()

        for thread in list(
            self._threads
        ):
            if thread.isRunning():
                thread.requestInterruption()
                thread.wait(1000)

        if (
            self._index_thread is not None
            and self._index_thread.isRunning()
        ):
            self._index_thread.requestInterruption()
            self._index_thread.wait(1000)

        super().closeEvent(event)

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

        for thread in self._threads:
            if thread.isRunning():
                thread.requestInterruption()

        thread = FileSearchThread(
            generation=generation,
            entries=self._search_index,
            query=query,
            max_results=self._max_results,
            fuzzy_threshold=(
                self._fuzzy_threshold
            ),
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

        self._search_index = list(entries)
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
        self._populate_tree(paths)

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

    def _populate_tree(
        self,
        paths: list[Path],
    ) -> None:
        self._tree.clear()

        if not paths:
            return

        root_label = (
            self._root_path.name
            or str(self._root_path)
        )
        root_item = QTreeWidgetItem(
            [root_label]
        )
        root_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            str(self._root_path),
        )
        root_item.setIcon(
            0,
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DirIcon
            ),
        )
        self._tree.addTopLevelItem(
            root_item
        )

        nodes: dict[
            Path,
            QTreeWidgetItem,
        ] = {
            self._root_path: root_item
        }
        result_paths = {path.resolve() for path in paths}

        for path in paths:
            try:
                relative = path.relative_to(
                    self._root_path
                )
            except ValueError:
                continue

            parent_path = self._root_path
            parent_item = root_item

            for part in relative.parts:
                current_path = (
                    parent_path / part
                )
                item = nodes.get(
                    current_path
                )

                if item is None:
                    item = QTreeWidgetItem(
                        [part]
                    )
                    item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        str(current_path),
                    )

                    standard_icon = (
                        QStyle.StandardPixmap.SP_DirIcon
                        if current_path.is_dir()
                        else QStyle.StandardPixmap.SP_FileIcon
                    )
                    item.setIcon(
                        0,
                        self.style().standardIcon(
                            standard_icon
                        ),
                    )
                    parent_item.addChild(
                        item
                    )
                    nodes[current_path] = item

                parent_item = item
                parent_path = current_path

        for node_path, node_item in nodes.items():
            is_hit = node_path.resolve() in result_paths
            node_item.setData(
                0,
                self._HIT_ROLE,
                is_hit,
            )
            if is_hit:
                font = node_item.font(0)
                font.setBold(True)
                node_item.setFont(0, font)

        root_item.setExpanded(True)
        self._tree.expandAll()

    def _on_item_double_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        self._activate_item(item)

    def _activate_item(self, item: QTreeWidgetItem) -> None:
        path_text = item.data(0, Qt.ItemDataRole.UserRole)
        if not path_text:
            return

        path = Path(str(path_text))
        if path.is_dir():
            item.setExpanded(not item.isExpanded())
            return

        self.latex_file_selected.emit(str(path.resolve()))
        self.close()

    def _focus_first_search_result(self) -> bool:
        iterator = self._tree.invisibleRootItem()

        def walk(parent: QTreeWidgetItem):
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

    def _remove_thread(
        self,
        thread: FileSearchThread,
    ) -> None:
        if thread in self._threads:
            self._threads.remove(
                thread
            )

        thread.deleteLater()

    def _remove_index_thread(
        self,
        thread: FileSearchIndexThread,
    ) -> None:
        if self._index_thread is thread:
            self._index_thread = None

        thread.deleteLater()
