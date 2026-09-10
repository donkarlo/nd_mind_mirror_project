"""Qt signals for per-source LaTeX preview cache state."""

from PySide6.QtCore import QObject, Signal


class LatexPreviewCacheSignalBus(QObject):
    """Keep cache-state signals on their own QMetaObject."""

    cached_preview_available = Signal(str)
    preview_source_empty = Signal(str)
