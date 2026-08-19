from pathlib import Path

from PySide6.QtCore import QObject, Signal


class Renderer(QObject):
    rendered = Signal(str)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source_path: Path | None = None

    def set_source_path(
        self,
        path: str | Path | None,
    ) -> None:
        self._source_path = (
            None
            if path is None
            else Path(path).expanduser().resolve()
        )
