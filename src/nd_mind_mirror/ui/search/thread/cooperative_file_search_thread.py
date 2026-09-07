"""Run fuzzy file search cooperatively so Python scoring never starves the GUI."""

from pathlib import Path

from PySide6.QtCore import QThread

from nd_mind_mirror.ui.search.thread.file_search_thread import (
    FileSearchThread,
)


class CooperativeFileSearchThread(FileSearchThread):
    """Yield briefly while scoring large indexes to keep typing responsive."""

    _YIELD_EVERY_ENTRIES = 192

    def run(self) -> None:
        if not self._tokens:
            self.results_ready.emit(
                self._generation,
                [],
                False,
            )
            return

        scored_results: list[tuple[float, int, str]] = []

        for index, (
            path_text,
            name_text,
            stem_text,
            normalized_name,
            normalized_stem,
            is_directory,
            relative_path,
        ) in enumerate(self._entries, start=1):
            if self.isInterruptionRequested():
                return

            score = self._score_name(
                name_text=name_text,
                stem_text=stem_text,
                name=normalized_name,
                stem=normalized_stem,
            )
            if (
                score is None
                and self._hierarchical_path_matching
                and not self._strict_filename_query
                and len(self._tokens) >= 2
            ):
                score = self._score_hierarchical_path(relative_path)

            if score is not None:
                scored_results.append(
                    (
                        score,
                        0 if is_directory else 1,
                        path_text,
                    )
                )

            if index % self._YIELD_EVERY_ENTRIES == 0:
                QThread.msleep(1)

        if self.isInterruptionRequested():
            return

        scored_results.sort(
            key=lambda item: (
                -item[0],
                item[1],
                len(Path(item[2]).name),
                item[2].casefold(),
            )
        )

        truncated = len(scored_results) > self._max_results
        results = [
            path
            for _, _, path in scored_results[:self._max_results]
        ]

        self.results_ready.emit(
            self._generation,
            results,
            truncated,
        )
