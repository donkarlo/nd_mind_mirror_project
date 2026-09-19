"""Event-driven reveal of filesystem paths in the Navigator tree."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QObject, Signal
from PySide6.QtWidgets import QAbstractItemView


class NavigatorPathRevealController(QObject):
    """Reveal one Navigator path as QFileSystemModel loads its ancestors."""

    path_revealed = Signal(str)

    def __init__(self, file_system_panel, parent=None) -> None:
        """Observe model loading and own the latest requested reveal."""
        super().__init__(parent)
        self._panel = file_system_panel
        self._model = file_system_panel._model
        self._proxy_model = file_system_panel._proxy_model
        self._tree = file_system_panel._tree
        self._pending_target: Path | None = None
        self._advancing = False

        self._model.directoryLoaded.connect(self._on_model_activity)
        self._model.rowsInserted.connect(self._on_rows_inserted)
        self._model.rootPathChanged.connect(self._on_model_activity)

    @property
    def pending_target(self) -> Path | None:
        """Return the newest path still waiting for filesystem-model data."""
        return self._pending_target

    def reveal(self, path: str | Path) -> None:
        """Reveal path now when possible, otherwise continue on model signals."""
        try:
            target = Path(path).expanduser().resolve(strict=False)
        except (OSError, TypeError, ValueError):
            self._pending_target = None
            return

        root = self._root_path()
        if not self._is_same_or_child(target, root):
            self._pending_target = None
            return

        self._pending_target = target
        self._advance_pending_reveal()

    def _advance_pending_reveal(self) -> None:
        """Load ancestors one at a time until the target index becomes valid."""
        if self._advancing or self._pending_target is None:
            return

        self._advancing = True
        try:
            target = self._pending_target
            if target is None:
                return

            root = self._root_path()
            for directory in self._directory_chain(target, root):
                source_index = self._model.index(str(directory))
                if not source_index.isValid():
                    return

                view_index = self._proxy_model.mapFromSource(source_index)
                if directory != root:
                    if not view_index.isValid():
                        self._pending_target = None
                        return
                    self._tree.expand(view_index)
                    self._panel._expanded_paths.add(str(directory))

                if self._model.canFetchMore(source_index):
                    self._model.fetchMore(source_index)
                    return

            source_index = self._model.index(str(target))
            if not source_index.isValid():
                return

            view_index = self._proxy_model.mapFromSource(source_index)
            if not view_index.isValid():
                self._pending_target = None
                return

            self._select_and_center(view_index)
            self._pending_target = None
            self.path_revealed.emit(str(target))
        finally:
            self._advancing = False

    def _select_and_center(self, view_index) -> None:
        """Apply one definitive selection after the target index is available."""
        selection_model = self._tree.selectionModel()
        if selection_model is not None:
            flags = (
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(view_index, flags)

        self._tree.setCurrentIndex(view_index)
        self._tree.scrollTo(
            view_index,
            QAbstractItemView.ScrollHint.PositionAtCenter,
        )

    def _on_model_activity(self, _path: str) -> None:
        """Continue the pending reveal after a directory/root finishes loading."""
        self._advance_pending_reveal()

    def _on_rows_inserted(self, _parent, _first: int, _last: int) -> None:
        """Continue when QFileSystemModel publishes newly loaded child rows."""
        self._advance_pending_reveal()

    def _root_path(self) -> Path:
        return Path(self._panel._root_path).expanduser().resolve(strict=False)

    @staticmethod
    def _directory_chain(target: Path, root: Path) -> tuple[Path, ...]:
        """Return root-to-parent directories needed before target can be indexed."""
        directory = target if target.is_dir() else target.parent
        try:
            relative = directory.relative_to(root)
        except ValueError:
            return ()

        result = [root]
        current = root
        for part in relative.parts:
            current = current / part
            result.append(current)
        return tuple(result)

    @staticmethod
    def _is_same_or_child(candidate: Path, parent: Path) -> bool:
        if candidate == parent:
            return True
        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False
