"""Cooperative indexed file search with shared scoring and cancellable yielding."""

from PySide6.QtCore import QThread

from nd_mind_mirror.ui.search.thread.file_search_thread import FileSearchThread


class CooperativeFileSearchThread(FileSearchThread):
    """Use the canonical file matcher while yielding during long scans."""

    _YIELD_EVERY_ENTRIES = 512

    def _yield_during_search(self, index: int) -> None:
        """Release the GIL periodically so the editor remains responsive."""
        if index % self._YIELD_EVERY_ENTRIES == 0:
            QThread.msleep(1)
