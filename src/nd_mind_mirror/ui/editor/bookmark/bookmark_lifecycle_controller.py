"""Keep persisted bookmarks consistent with the lifetime of workspace files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer


class BookmarkLifecycleController(QObject):
    """Remove stale bookmark entries when their files disappear from the workspace."""

    def __init__(self, editor_panel, file_system_panel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._file_system_panel = file_system_panel
        self._file_system_panel.path_deleted.connect(self.remove_for_deleted_path)
        QTimer.singleShot(0, self.prune_missing_files)

    def remove_for_deleted_path(self, path_text: str) -> None:
        """Remove bookmarks for one deleted file or every file below a deleted folder."""
        try:
            deleted_path = Path(path_text).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            return

        current = self._editor_panel.bookmarks()
        filtered = {
            raw_path: bookmarks
            for raw_path, bookmarks in current.items()
            if not self._is_same_or_child(raw_path, deleted_path)
        }
        self._replace_if_changed(current, filtered)

    def prune_missing_files(self) -> None:
        """Remove persisted bookmark groups whose files no longer exist at startup."""
        current = self._editor_panel.bookmarks()
        filtered: dict[str, list[dict[str, object]]] = {}
        for raw_path, bookmarks in current.items():
            try:
                candidate = Path(raw_path).expanduser().resolve()
            except (OSError, TypeError, ValueError):
                continue
            if candidate.is_file():
                filtered[str(candidate)] = bookmarks
        self._replace_if_changed(current, filtered)

    def _replace_if_changed(
        self,
        current: dict[str, list[dict[str, object]]],
        filtered: dict[str, list[dict[str, object]]],
    ) -> None:
        if filtered == current:
            return
        self._editor_panel.set_bookmarks(filtered)
        self._editor_panel.bookmarks_changed.emit(self._editor_panel.bookmarks())

    @staticmethod
    def _is_same_or_child(raw_path: str, parent: Path) -> bool:
        try:
            candidate = Path(raw_path).expanduser().resolve()
            candidate.relative_to(parent)
            return True
        except (OSError, TypeError, ValueError):
            return False
