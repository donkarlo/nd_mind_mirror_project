"""Publish and resolve real local-file clipboard payloads for Navigator operations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication


class FileClipboardMimeDataController:
    """Keep Navigator file copy/cut distinct from pixel/image clipboard data."""

    MIME_TYPE = "application/x-nd-mind-mirror-file-clipboard"

    def __init__(self, clipboard: QClipboard | None = None) -> None:
        self._clipboard = clipboard or QApplication.clipboard()

    @property
    def clipboard(self) -> QClipboard:
        return self._clipboard

    def publish_paths(self, paths: list[Path]) -> None:
        """Replace the system clipboard with one canonical local-file payload."""
        mime_data = self.mime_data_for_paths(paths)
        self._clipboard.setMimeData(mime_data)

    @classmethod
    def mime_data_for_paths(cls, paths: list[Path]) -> QMimeData:
        """Build a standard file-URL payload plus a Mind Mirror ownership marker."""
        canonical: list[Path] = []
        for raw_path in paths:
            try:
                path = Path(raw_path).expanduser().resolve(strict=False)
            except OSError:
                continue
            if path in canonical:
                continue
            canonical.append(path)

        mime_data = QMimeData()
        mime_data.setUrls(
            [QUrl.fromLocalFile(str(path)) for path in canonical]
        )
        mime_data.setText("\n".join(str(path) for path in canonical))
        mime_data.setData(cls.MIME_TYPE, b"1")
        return mime_data

    @classmethod
    def is_mind_mirror_file_payload(cls, mime_data: QMimeData | None) -> bool:
        return bool(
            mime_data is not None
            and mime_data.hasFormat(cls.MIME_TYPE)
        )

    @staticmethod
    def local_paths(mime_data: QMimeData | None) -> list[Path]:
        """Return unique existing local files/folders from a standard URI list."""
        if mime_data is None or not mime_data.hasUrls():
            return []

        result: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            candidate = Path(url.toLocalFile()).expanduser()
            try:
                candidate = candidate.resolve(strict=False)
            except OSError:
                continue
            if not (candidate.exists() or candidate.is_symlink()):
                continue
            if candidate not in result:
                result.append(candidate)
        return result
