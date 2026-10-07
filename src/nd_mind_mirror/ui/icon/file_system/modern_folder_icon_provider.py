from PySide6.QtCore import QFileInfo, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFileIconProvider


class ModernFolderIconProvider(QFileIconProvider):
    """Provide a clean light-blue folder icon while preserving normal file icons."""

    _DEFAULT_FOLDER_COLOR = "#69B7F4"

    def __init__(self, folder_color: str = _DEFAULT_FOLDER_COLOR) -> None:
        super().__init__()
        self._folder_color = self._validated_color(folder_color)
        self._folder_icon = self._build_folder_icon()

    def set_folder_color(self, color: str) -> None:
        candidate = self._validated_color(color)
        if candidate == self._folder_color:
            return
        self._folder_color = candidate
        self._folder_icon = self._build_folder_icon()

    def icon(self, value):
        if isinstance(value, QFileInfo) and value.isDir():
            return self._folder_icon
        return super().icon(value)

    def _build_folder_icon(self) -> QIcon:
        icon = QIcon()
        for size in (16, 20, 24, 32):
            icon.addPixmap(self._folder_pixmap(size))
        return icon

    def _folder_pixmap(self, size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        scale = size / 24.0
        body = QPainterPath()
        body.addRoundedRect(
            QRectF(1.8 * scale, 6.6 * scale, 20.4 * scale, 14.2 * scale),
            2.4 * scale,
            2.4 * scale,
        )
        tab = QPainterPath()
        tab.addRoundedRect(
            QRectF(3.0 * scale, 3.6 * scale, 9.8 * scale, 6.3 * scale),
            2.0 * scale,
            2.0 * scale,
        )

        border = self._folder_color.darker(112)
        painter.setPen(QPen(border, max(0.8, 0.9 * scale)))
        painter.setBrush(self._folder_color)
        painter.drawPath(tab)
        painter.drawPath(body)

        highlight = QColor(self._folder_color)
        highlight.setAlpha(105)
        painter.setPen(QPen(highlight.lighter(128), max(0.7, 0.8 * scale)))
        painter.drawLine(
            int(3.6 * scale),
            int(8.4 * scale),
            int(20.3 * scale),
            int(8.4 * scale),
        )
        painter.end()
        return pixmap

    @classmethod
    def _validated_color(cls, value: str) -> QColor:
        color = QColor(str(value))
        if color.isValid():
            return color
        return QColor(cls._DEFAULT_FOLDER_COLOR)
