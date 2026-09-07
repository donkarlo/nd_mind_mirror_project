"""Build the file-search index cooperatively so repository scans do not stall typing."""

from pathlib import Path
import os

from PySide6.QtCore import QThread

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import (
    SearchIgnoreMatcher,
)
from nd_mind_mirror.ui.search.thread.file_search_index_thread import (
    FileSearchIndexThread,
)


class CooperativeFileSearchIndexThread(FileSearchIndexThread):
    """Yield during large workspace scans while preserving the canonical index format."""

    _YIELD_EVERY_DIRECTORIES = 32
    _YIELD_EVERY_FILES = 256

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
