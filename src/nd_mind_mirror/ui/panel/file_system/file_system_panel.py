from pathlib import Path
import shutil

from PySide6.QtCore import (
    QDir,
    QEvent,
    QItemSelectionModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QTreeView,
)

from nd_mind_mirror.ui.model.file_system.ignored_file_system_proxy_model import (
    IgnoredFileSystemProxyModel,
)
from nd_mind_mirror.ui.panel.base.panel import Panel


class FileSystemPanel(Panel):
    latex_file_selected = Signal(str)

    _ACTIVATABLE_SUFFIXES = {
        ".tex", ".yaml", ".yml", ".pdf",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
        ".svg", ".tif", ".tiff",
    }
    state_changed = Signal()
    path_renamed = Signal(str, str)
    path_deleted = Signal(str)
    path_created = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("File System", parent)

        self._expanded_paths: set[str] = set()
        self._pending_reveal: Path | None = None
        self._root_path = Path.home().resolve()
        self._ignore_file_path: Path | None = None

        self.setMinimumWidth(90)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel(
            "File System",
            self,
        )

        self._model = QFileSystemModel(self)
        self._model.setFilter(
            QDir.Filter.AllDirs
            | QDir.Filter.Files
            | QDir.Filter.NoDotAndDotDot
        )
        self._model.setRootPath(
            str(self._root_path)
        )

        self._proxy_model = IgnoredFileSystemProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.configure(
            self._root_path,
            self._ignore_file_path,
        )

        self._tree = QTreeView(self)
        self._tree.setMinimumWidth(0)
        self._tree.setModel(self._proxy_model)
        self._tree.setRootIndex(
            self._proxy_model.mapFromSource(
                self._model.index(str(self._root_path))
            )
        )
        self._tree.setAnimated(False)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(
            0,
            Qt.SortOrder.AscendingOrder,
        )
        self._tree.setIndentation(10)
        self._tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        for column in range(1, 4):
            self._tree.setColumnHidden(
                column,
                True,
            )

        self._tree.header().setStretchLastSection(
            True
        )

        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        # Double-click is handled explicitly in eventFilter(). Consuming the
        # viewport event prevents QTreeView from also expanding/recentering
        # the item, which previously caused missed file activations and jumps.
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.viewport().installEventFilter(self)

        self._tree.clicked.connect(
            self._on_clicked
        )
        self._tree.expanded.connect(
            self._on_expanded
        )
        self._tree.collapsed.connect(
            self._on_collapsed
        )
        self._tree.customContextMenuRequested.connect(
            self._show_context_menu
        )

        self.panel_layout.addWidget(
            self._label
        )
        self.panel_layout.addWidget(
            self._tree,
            1,
        )

    def apply_settings(
        self,
        indent_width: int,
        root_path: str | Path,
        ignore_file_path: str | Path | None,
        row_height: int = 24,
    ) -> None:
        new_root = Path(
            root_path
        ).expanduser().resolve()
        new_ignore = (
            Path(ignore_file_path).expanduser().resolve()
            if ignore_file_path is not None
            else None
        )
        root_changed = new_root != self._root_path

        self._root_path = new_root
        self._ignore_file_path = new_ignore
        self._tree.setIndentation(
            max(
                int(indent_width),
                1,
            )
        )
        self._tree.setStyleSheet(
            f"QTreeView::item {{ min-height: {max(int(row_height), 18)}px; }}"
        )

        self._model.setRootPath(
            str(self._root_path)
        )
        self._proxy_model.configure(
            self._root_path,
            self._ignore_file_path,
        )

        self._apply_root_index()
        QTimer.singleShot(100, self._apply_root_index)
        QTimer.singleShot(400, self._apply_root_index)
        self._label.setText(
            f"File System — {self._root_path}"
        )

        if root_changed:
            self._expanded_paths = {
                value
                for value in self._expanded_paths
                if self._is_same_or_child(
                    Path(value),
                    self._root_path,
                )
            }
            self._pending_reveal = None

    def _apply_root_index(self) -> None:
        root_index = self._view_index_for_path(
            self._root_path
        )
        if root_index.isValid():
            self._tree.setRootIndex(root_index)

    def expanded_paths(self) -> list[str]:
        return sorted(
            (
                path
                for path in self._expanded_paths
                if self._is_same_or_child(
                    Path(path),
                    self._root_path,
                )
            ),
            key=lambda value: (
                value.count("/"),
                value,
            ),
        )

    def selected_path(self) -> str:
        index = self._tree.currentIndex()

        if not index.isValid():
            return ""

        return self._path_for_view_index(index)

    def select_path(
        self,
        path: str | Path,
    ) -> None:
        target = Path(
            path
        ).expanduser().resolve()

        if not self._is_same_or_child(
            target,
            self._root_path,
        ):
            return

        current_path = self.selected_path()
        if current_path:
            try:
                if Path(current_path).resolve() == target:
                    # The navigator already owns this selection (for
                    # example after a double-click). Do not recenter it or
                    # schedule delayed reveal passes, which otherwise cause
                    # the visible tree to jump away and back.
                    self._pending_reveal = None
                    return
            except OSError:
                pass

        self._pending_reveal = target
        self._reveal_path(target)

        QTimer.singleShot(
            80,
            lambda item=target:
            self._reveal_path(item),
        )
        QTimer.singleShot(
            250,
            lambda item=target:
            self._reveal_path(item),
        )

    def restore_state(
        self,
        expanded_paths: list[str],
        selected_path: str,
    ) -> None:
        self._expanded_paths = {
            str(candidate)
            for path in expanded_paths
            if path
            for candidate in [
                Path(path).expanduser().resolve()
            ]
            if self._is_same_or_child(
                candidate,
                self._root_path,
            )
        }

        def apply() -> None:
            for path in sorted(
                self._expanded_paths,
                key=lambda value: value.count("/"),
            ):
                index = self._view_index_for_path(path)

                if index.isValid():
                    self._tree.expand(index)

            if selected_path:
                self.select_path(
                    selected_path
                )

        QTimer.singleShot(150, apply)
        QTimer.singleShot(700, apply)
        QTimer.singleShot(1600, apply)

    def _reveal_path(
        self,
        target: Path,
    ) -> None:
        if (
            self._pending_reveal is not None
            and target != self._pending_reveal
        ):
            return

        if not self._is_same_or_child(
            target,
            self._root_path,
        ):
            return

        index = self._view_index_for_path(target)

        if not index.isValid():
            return

        parents = []
        parent_index = index.parent()

        while parent_index.isValid():
            parents.append(parent_index)
            parent_path = self._path_for_view_index(
                parent_index
            )
            if Path(parent_path) == self._root_path:
                break
            parent_index = parent_index.parent()

        for ancestor_index in reversed(parents):
            self._tree.expand(
                ancestor_index
            )

            ancestor_path = self._path_for_view_index(
                ancestor_index
            )
            if ancestor_path:
                self._expanded_paths.add(
                    ancestor_path
                )

        selection_model = (
            self._tree.selectionModel()
        )

        if selection_model is not None:
            flags = (
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(
                index,
                flags,
            )

        self._tree.setCurrentIndex(index)
        self._tree.scrollTo(
            index,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def _on_clicked(self, index) -> None:
        if not index.isValid():
            return

        # A single click only changes the navigator selection. Opening a
        # document is intentionally reserved for double-click so browsing
        # the tree cannot create tabs accidentally.
        self.state_changed.emit()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self._tree.viewport()
            and event.type() == QEvent.Type.MouseButtonDblClick
            and event.button() == Qt.MouseButton.LeftButton
        ):
            index = self._tree.indexAt(
                event.position().toPoint()
            )
            if index.isValid():
                self._activate_index(index)
            event.accept()
            return True

        return super().eventFilter(watched, event)

    def _activate_index(self, index) -> None:
        if not index.isValid():
            return

        source_index = self._source_index(index)
        if not source_index.isValid():
            return

        if self._model.isDir(source_index):
            if self._tree.isExpanded(index):
                self._tree.collapse(index)
            else:
                self._tree.expand(index)
            self.state_changed.emit()
            return

        path = Path(
            self._model.filePath(source_index)
        )

        if path.suffix.lower() in self._ACTIVATABLE_SUFFIXES:
            self.latex_file_selected.emit(
                str(path)
            )

        self.state_changed.emit()

    def _on_expanded(self, index) -> None:
        path = self._path_for_view_index(index)

        if path:
            self._expanded_paths.add(path)

        self.state_changed.emit()

    def _on_collapsed(self, index) -> None:
        path = self._path_for_view_index(index)

        if path:
            self._expanded_paths.discard(path)

        self.state_changed.emit()

    def _show_context_menu(
        self,
        position,
    ) -> None:
        index = self._tree.indexAt(position)

        if not index.isValid():
            index = self._tree.currentIndex()

        if not index.isValid():
            return

        self._tree.setCurrentIndex(index)
        path = Path(
            self._path_for_view_index(index)
        )

        menu = QMenu(self)

        new_latex_file_action = menu.addAction(
            "New LaTeX File..."
        )
        new_file_action = menu.addAction(
            "New File..."
        )
        new_folder_action = menu.addAction(
            "New Folder..."
        )
        menu.addSeparator()
        rename_action = menu.addAction(
            "Rename..."
        )
        delete_action = menu.addAction(
            "Delete..."
        )

        if path == self._root_path:
            rename_action.setEnabled(False)
            delete_action.setEnabled(False)

        chosen = menu.exec(
            self._tree.viewport().mapToGlobal(
                position
            )
        )

        if chosen == new_latex_file_action:
            self._create_file(
                path,
                latex=True,
            )
        elif chosen == new_file_action:
            self._create_file(
                path,
                latex=False,
            )
        elif chosen == new_folder_action:
            self._create_folder(path)
        elif chosen == rename_action:
            self._rename_path(path)
        elif chosen == delete_action:
            self._delete_path(path)

    def _target_directory(
        self,
        selected_path: Path,
    ) -> Path:
        if selected_path.is_dir():
            return selected_path

        return selected_path.parent

    def _create_file(
        self,
        selected_path: Path,
        latex: bool,
    ) -> None:
        directory = self._target_directory(
            selected_path
        )

        title = (
            "New LaTeX File"
            if latex
            else "New File"
        )

        name, accepted = QInputDialog.getText(
            self,
            title,
            "File name:",
        )

        if not accepted:
            return

        normalized = name.strip()

        if not normalized:
            return

        candidate = Path(normalized)

        if (
            latex
            and candidate.suffix == ""
        ):
            candidate = candidate.with_suffix(
                ".tex"
            )

        target = directory / candidate

        if target.exists():
            QMessageBox.warning(
                self,
                title,
                f"{target.name} already exists.",
            )
            return

        try:
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            target.write_text(
                "",
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                title,
                str(exc),
            )
            return

        self._proxy_model.invalidateFilter()
        self.path_created.emit(
            str(target.resolve())
        )
        self.select_path(target)
        self.state_changed.emit()

    def _create_folder(
        self,
        selected_path: Path,
    ) -> None:
        directory = self._target_directory(
            selected_path
        )

        name, accepted = QInputDialog.getText(
            self,
            "New Folder",
            "Folder name:",
        )

        if not accepted:
            return

        normalized = name.strip()

        if not normalized:
            return

        target = directory / normalized

        if target.exists():
            QMessageBox.warning(
                self,
                "New Folder",
                f"{target.name} already exists.",
            )
            return

        try:
            target.mkdir(
                parents=False,
                exist_ok=False,
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "New Folder",
                str(exc),
            )
            return

        self._proxy_model.invalidateFilter()
        self.path_created.emit(
            str(target.resolve())
        )
        self.select_path(target)
        self.state_changed.emit()

    def _rename_path(
        self,
        path: Path,
    ) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Rename",
            "New name:",
            QLineEdit.EchoMode.Normal,
            path.name,
        )

        if not accepted:
            return

        normalized = name.strip()

        if (
            not normalized
            or normalized == path.name
        ):
            return

        target = path.with_name(normalized)

        if target.exists():
            QMessageBox.warning(
                self,
                "Rename",
                f"{target.name} already exists.",
            )
            return

        old_path = path.resolve()

        try:
            path.rename(target)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Rename",
                str(exc),
            )
            return

        new_path = target.resolve()

        self._expanded_paths = {
            self._renamed_state_path(
                value,
                old_path,
                new_path,
            )
            for value in self._expanded_paths
        }

        self._proxy_model.invalidateFilter()
        self.path_renamed.emit(
            str(old_path),
            str(new_path),
        )
        self.select_path(new_path)
        self.state_changed.emit()

    def _delete_path(
        self,
        path: Path,
    ) -> None:
        kind = (
            "folder"
            if path.is_dir()
            else "file"
        )

        decision = QMessageBox.warning(
            self,
            "Delete",
            f"Delete this {kind} permanently?\n\n{path}",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if (
            decision
            != QMessageBox.StandardButton.Yes
        ):
            return

        resolved = path.resolve()

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Delete",
                str(exc),
            )
            return

        self._expanded_paths = {
            value
            for value in self._expanded_paths
            if not self._is_same_or_child(
                Path(value),
                resolved,
            )
        }

        self._proxy_model.invalidateFilter()
        self.path_deleted.emit(
            str(resolved)
        )
        self.state_changed.emit()

    def _source_index(self, view_index):
        return self._proxy_model.mapToSource(
            view_index
        )

    def _path_for_view_index(
        self,
        view_index,
    ) -> str:
        if not view_index.isValid():
            return ""

        source_index = self._source_index(
            view_index
        )
        return self._model.filePath(
            source_index
        )

    def _view_index_for_path(
        self,
        path: str | Path,
    ):
        source_index = self._model.index(
            str(Path(path))
        )
        return self._proxy_model.mapFromSource(
            source_index
        )

    def _renamed_state_path(
        self,
        value: str,
        old_path: Path,
        new_path: Path,
    ) -> str:
        candidate = Path(value)

        try:
            relative = candidate.relative_to(
                old_path
            )
        except ValueError:
            return value

        return str(
            new_path / relative
        )

    def _is_same_or_child(
        self,
        candidate: Path,
        parent: Path,
    ) -> bool:
        if candidate == parent:
            return True

        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False
