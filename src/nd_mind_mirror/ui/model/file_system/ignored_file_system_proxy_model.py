from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import (
    SearchIgnoreMatcher,
)


class IgnoredFileSystemProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._root_path = Path.home().resolve()
        self._matcher = SearchIgnoreMatcher()
        self.setDynamicSortFilter(True)

    def configure(
        self,
        root_path: str | Path,
        ignore_file_path: str | Path | None,
    ) -> None:
        self._root_path = Path(
            root_path
        ).expanduser().resolve()
        self._matcher = SearchIgnoreMatcher.from_file(
            ignore_file_path
        )
        self.invalidateFilter()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent,
    ) -> bool:
        model = self.sourceModel()
        if model is None:
            return False

        index = model.index(
            source_row,
            0,
            source_parent,
        )
        if not index.isValid():
            return False

        path_text = model.filePath(index)
        if not path_text:
            return False

        path = Path(path_text)

        # QFileSystemModel indexes the configured root through its
        # ancestors. Keep those ancestors in the proxy so mapFromSource()
        # can produce a valid index for the configured root. The view itself
        # is rooted at _root_path, so the ancestors are never shown.
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
