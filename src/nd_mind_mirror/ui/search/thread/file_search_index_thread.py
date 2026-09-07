"""Build the reusable file-search index without starving the Qt event loop."""

from pathlib import Path
import os

from PySide6.QtCore import QThread, Signal

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import (
    SearchIgnoreMatcher,
)


class FileSearchIndexThread(QThread):
    """Scan the workspace in a cancellable worker and periodically yield the GIL."""

    index_ready = Signal(int, object)

    _YIELD_EVERY_DIRECTORIES = 32
    _YIELD_EVERY_FILES = 256

    def __init__(
        self,
        generation: int,
        root_path: str | Path,
        ignore_file_path: str | Path | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._generation = generation
        self._root_path = Path(
            root_path
        ).expanduser().resolve()
        self._ignore_file_path = (
            Path(ignore_file_path).expanduser().resolve()
            if ignore_file_path is not None
            else None
        )

    def run(self) -> None:
        entries: list[
            tuple[str, str, str, str, str, bool, str]
        ] = []
        matcher = SearchIgnoreMatcher.from_file(
            self._ignore_file_path
        )
        visited_directories = 0
        visited_files = 0

        try:
            walker = os.walk(
                self._root_path,
                topdown=True,
                followlinks=False,
                onerror=lambda error: None,
            )

            for current_root, directories, files in walker:
                if self.isInterruptionRequested():
                    return

                current_path = Path(current_root)
                kept_directories = []

                for name in directories:
                    if self.isInterruptionRequested():
                        return

                    path = current_path / name
                    if matcher.is_ignored(
                        path,
                        self._root_path,
                        is_directory=True,
                    ):
                        continue

                    kept_directories.append(name)
                    entries.append(
                        self._entry(path, name, True)
                    )
                    visited_directories += 1

                    if (
                        visited_directories
                        % self._YIELD_EVERY_DIRECTORIES
                        == 0
                    ):
                        QThread.msleep(1)

                directories[:] = kept_directories

                for name in files:
                    if self.isInterruptionRequested():
                        return

                    path = current_path / name
                    if matcher.is_ignored(
                        path,
                        self._root_path,
                        is_directory=False,
                    ):
                        continue

                    entries.append(
                        self._entry(path, name, False)
                    )
                    visited_files += 1

                    if (
                        visited_files
                        % self._YIELD_EVERY_FILES
                        == 0
                    ):
                        QThread.msleep(1)
        except OSError:
            entries = []

        if self.isInterruptionRequested():
            return

        self.index_ready.emit(
            self._generation,
            entries,
        )

    def _entry(
        self,
        path: Path,
        name: str,
        is_directory: bool,
    ) -> tuple[str, str, str, str, str, bool, str]:
        stem = Path(name).stem
        try:
            relative_path = path.relative_to(
                self._root_path
            ).as_posix()
        except ValueError:
            relative_path = path.name

        return (
            str(path),
            name,
            stem,
            name.casefold(),
            stem.casefold(),
            is_directory,
            relative_path.casefold(),
        )
