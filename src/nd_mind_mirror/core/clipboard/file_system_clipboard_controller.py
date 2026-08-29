from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QFileSystemModel, QMessageBox, QTreeView


class FileSystemClipboardController(QObject):
    """Provide Ctrl+C/Ctrl+V copy semantics for QFileSystemModel navigators."""

    _installed_instance: "FileSystemClipboardController | None" = None

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self._copied_path: Path | None = None
        self._clipboard = application.clipboard()
        self._clipboard.dataChanged.connect(self._on_system_clipboard_changed)

    @classmethod
    def install_once(
        cls,
        application: QApplication | None,
    ) -> "FileSystemClipboardController | None":
        if application is None:
            return None

        if cls._installed_instance is None:
            controller = cls(application)
            application.installEventFilter(controller)
            cls._installed_instance = controller

        return cls._installed_instance

    @property
    def has_active_copy(self) -> bool:
        source = self._copied_path
        return source is not None and source.exists()

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() != QEvent.Type.KeyPress
            or not isinstance(watched, QTreeView)
        ):
            return super().eventFilter(watched, event)

        if not bool(
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            return super().eventFilter(watched, event)

        if event.key() == Qt.Key.Key_C:
            selected_path = self._selected_path(watched)
            if selected_path is None or not selected_path.exists():
                return super().eventFilter(watched, event)

            self._copied_path = selected_path
            event.accept()
            return True

        if event.key() != Qt.Key.Key_V:
            return super().eventFilter(watched, event)

        source = self._copied_path
        if source is None or not source.exists():
            self._copied_path = None
            return super().eventFilter(watched, event)

        selected_path = self._selected_path(watched)
        if selected_path is None:
            return super().eventFilter(watched, event)

        if source.is_dir() and selected_path == source:
            destination = source.parent
        else:
            destination = (
                selected_path
                if selected_path.is_dir()
                else selected_path.parent
            )

        try:
            copied_path = self._copy(source, destination)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                watched,
                "Copy",
                str(exc),
            )
            event.accept()
            return True

        self._select_path_when_available(watched, copied_path)
        event.accept()
        return True

    def _on_system_clipboard_changed(self) -> None:
        # Internal navigator copies intentionally do not alter the system
        # clipboard. A later external copy therefore exits navigator-copy mode.
        self._copied_path = None

    def _selected_path(self, tree: QTreeView) -> Path | None:
        index = tree.currentIndex()
        model = tree.model()
        if model is None or not index.isValid():
            return None

        while not isinstance(model, QFileSystemModel):
            map_to_source = getattr(model, "mapToSource", None)
            source_model = getattr(model, "sourceModel", None)
            if not callable(map_to_source) or not callable(source_model):
                return None
            index = map_to_source(index)
            model = source_model()
            if model is None or not index.isValid():
                return None

        path_text = model.filePath(index)
        if not path_text:
            return None

        try:
            return Path(path_text).expanduser().resolve()
        except OSError:
            return None

    def _copy(
        self,
        source: Path,
        destination: Path,
    ) -> Path:
        destination = destination.expanduser().resolve()
        if not destination.is_dir():
            raise ValueError("Paste destination is not a directory.")

        if source.is_dir() and self._is_same_or_child(destination, source):
            raise ValueError("A folder cannot be copied inside itself.")

        target = self._next_available_target(source, destination)
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                symlinks=True,
            )
        else:
            shutil.copy2(
                source,
                target,
                follow_symlinks=False,
            )
        return target.resolve()

    @staticmethod
    def _next_available_target(
        source: Path,
        destination: Path,
    ) -> Path:
        candidate = destination / source.name
        if not candidate.exists():
            return candidate

        if source.is_dir():
            base_name = source.name
            suffix = ""
        else:
            suffix = source.suffix
            base_name = (
                source.name[: -len(suffix)]
                if suffix
                else source.name
            )

        counter = 1
        while True:
            candidate = destination / f"{base_name}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    @staticmethod
    def _is_same_or_child(
        path: Path,
        parent: Path,
    ) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _select_path_when_available(
        self,
        tree: QTreeView,
        path: Path,
    ) -> None:
        for delay in (100, 300, 700):
            QTimer.singleShot(
                delay,
                lambda view=tree, target=path: self._select_path(
                    view,
                    target,
                ),
            )

    def _select_path(
        self,
        tree: QTreeView,
        path: Path,
    ) -> None:
        model = tree.model()
        if model is None:
            return

        proxies = []
        source_model = model
        while not isinstance(source_model, QFileSystemModel):
            source_getter = getattr(source_model, "sourceModel", None)
            if not callable(source_getter):
                return
            proxies.append(source_model)
            source_model = source_getter()
            if source_model is None:
                return

        index = source_model.index(str(path))
        if not index.isValid():
            return

        for proxy in reversed(proxies):
            index = proxy.mapFromSource(index)
            if not index.isValid():
                return

        tree.setCurrentIndex(index)
        tree.scrollTo(index)
