from pathlib import Path
import os

from PySide6.QtCore import QThread, Signal

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import (
    SearchIgnoreMatcher,
)


class FileSearchIndexThread(QThread):
    index_ready = Signal(int, object)

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
            tuple[str, str, str, str, str, bool]
        ] = []
        matcher = SearchIgnoreMatcher.from_file(
            self._ignore_file_path
        )

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

                directories[:] = kept_directories

                for name in files:
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
    ) -> tuple[str, str, str, str, str, bool]:
        stem = Path(name).stem
        return (
            str(path),
            name,
            stem,
            name.casefold(),
            stem.casefold(),
            is_directory,
        )
