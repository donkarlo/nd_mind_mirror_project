from PySide6.QtWidgets import QVBoxLayout, QWidget


class Panel(QWidget):
    def __init__(
        self,
        title: str,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._title = title
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            6,
            6,
            6,
            6,
        )
        self._layout.setSpacing(6)

    @property
    def panel_layout(self) -> QVBoxLayout:
        return self._layout
