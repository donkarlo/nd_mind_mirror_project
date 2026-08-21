"""Filter ignored workspace paths and sort directories before files alphabetically."""

from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher


class IgnoredFileSystemProxyModel(QSortFilterProxyModel):
    """Keep ignored paths out of Navigator while enforcing folder-first case-insensitive sorting."""

    def __init__(self, parent=None) -> None:
        """Initialize a dynamic proxy rooted at the user's home directory until configured."""
        super().__init__(parent)
        self._root_path = Path.home().resolve()
        self._matcher = SearchIgnoreMatcher()
        self.setDynamicSortFilter(True)

    def configure(
        self,
        root_path: str | Path,
        ignore_file_path: str | Path | None,
    ) -> None:
        """Set the visible workspace root and load its optional ignore-rule file."""
        self._root_path = Path(root_path).expanduser().resolve()
        self._matcher = SearchIgnoreMatcher.from_file(ignore_file_path)
        self.invalidateFilter()
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """Accept root ancestors and non-ignored descendants while rejecting unrelated paths."""
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

        # QFileSystemModel needs root ancestors in the proxy for mapFromSource().
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

    def lessThan(self, left, right) -> bool:
        """Order directories first and then compare names alphabetically without case sensitivity."""
        model = self.sourceModel()
        if model is None:
            return super().lessThan(left, right)

        left_is_dir = bool(model.isDir(left))
        right_is_dir = bool(model.isDir(right))
        if left_is_dir != right_is_dir:
            return left_is_dir

        left_name = str(model.fileName(left))
        right_name = str(model.fileName(right))
        left_folded = left_name.casefold()
        right_folded = right_name.casefold()
        if left_folded != right_folded:
            return left_folded < right_folded
        return left_name < right_name
