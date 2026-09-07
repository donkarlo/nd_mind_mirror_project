"""Filter ignored workspace paths and sort directories before files."""

import re
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher


class IgnoredFileSystemProxyModel(QSortFilterProxyModel):
    """Keep ignored paths out of Navigator and refresh after filesystem mutations."""

    def __init__(self, parent=None) -> None:
        """Initialize a dynamic proxy rooted at the user's home directory."""
        super().__init__(parent)
        self._root_path = Path.home().resolve()
        self._matcher = SearchIgnoreMatcher()
        self.setDynamicSortFilter(True)

    def configure(
        self,
        root_path: str | Path,
        ignore_file_path: str | Path | None,
    ) -> None:
        """Set the workspace root and reload ignore rules."""
        self._root_path = Path(root_path).expanduser().resolve()
        self._matcher = SearchIgnoreMatcher.from_file(ignore_file_path)
        self.refresh_after_filesystem_change()

    def invalidateFilter(self) -> None:
        """Refresh the proxy after an explicit filesystem mutation.

        QFileSystemModel already watches ordinary external changes. Mind Mirror
        calls this method specifically after create/rename/move/delete/paste;
        those explicit operations must not leave stale proxy rows behind.
        """
        self.refresh_after_filesystem_change()

    def refresh_after_filesystem_change(self) -> None:
        """Rebuild proxy mappings from the current QFileSystemModel state."""
        super().invalidateFilter()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Accept root ancestors and non-ignored descendants."""
        model = self.sourceModel()
        if model is None:
            return False

        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False

        path_text = model.filePath(index)
        if not path_text:
            return False
        path = Path(path_text)

        if path == self._root_path:
            return True

        try:
            path.relative_to(self._root_path)
            is_inside_root = True
        except ValueError:
            is_inside_root = False

        if not is_inside_root:
            try:
                self._root_path.relative_to(path)
                return True
            except ValueError:
                return False

        return not self._matcher.is_ignored(
            path=path,
            root_path=self._root_path,
            is_directory=model.isDir(index),
        )

    @staticmethod
    def _natural_name_key(name: str) -> tuple[tuple[int, object], ...]:
        """Return a case-insensitive key where digit runs compare numerically."""
        parts = re.split(r"([0-9]+)", str(name).casefold())
        key: list[tuple[int, object]] = []
        for part in parts:
            if not part:
                continue
            if part.isdigit():
                key.append((1, int(part)))
            else:
                key.append((0, part))
        return tuple(key)

    def lessThan(self, left, right) -> bool:
        """Order folders first, then sort folders/files independently by name."""
        model = self.sourceModel()
        if model is None:
            return super().lessThan(left, right)

        left_is_dir = bool(model.isDir(left))
        right_is_dir = bool(model.isDir(right))
        if left_is_dir != right_is_dir:
            return left_is_dir

        left_name = str(model.fileName(left))
        right_name = str(model.fileName(right))
        left_key = self._natural_name_key(left_name)
        right_key = self._natural_name_key(right_name)
        if left_key != right_key:
            return left_key < right_key

        left_folded = left_name.casefold()
        right_folded = right_name.casefold()
        if left_folded != right_folded:
            return left_folded < right_folded
        return left_name < right_name
