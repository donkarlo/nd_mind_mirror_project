from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
)


class LatexFormatToolbar(QWidget):
    """Compact source-format toolbar for common LaTeX wrappers."""

    bold_requested = Signal()
    highlight_requested = Signal(str)
    apply_settings_requested = Signal()

    _HIGHLIGHT_COLORS = (
        ("Pale yellow", "yellow!20", "#fff6bf"),
        ("Pale green", "green!15", "#dcf4dc"),
        ("Pale blue", "blue!12", "#dfefff"),
        ("Pale cyan", "cyan!12", "#ddf7f7"),
        ("Pale orange", "orange!18", "#ffe8c7"),
        ("Pale red", "red!12", "#ffe0e0"),
        ("Pale purple", "violet!12", "#eee1f7"),
        ("Pale gray", "black!8", "#ededed"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._bold_button = QToolButton(self)
        self._bold_button.setText("B")
        self._bold_button.setToolTip("Bold selection (Ctrl+B)")
        self._bold_button.setFixedSize(30, 30)
        self._bold_button.setStyleSheet(
            "QToolButton { font-weight: 700; border: 1px solid #c7ccd1; "
            "border-radius: 3px; background: #ffffff; }"
            "QToolButton:hover { background: #eef5ff; border-color: #6aa9e9; }"
        )
        self._bold_button.clicked.connect(self.bold_requested.emit)

        self._highlight_button = QToolButton(self)
        self._highlight_button.setText("H")
        self._highlight_button.setToolTip("Highlight selected text")
        self._highlight_button.setFixedSize(30, 30)
        self._highlight_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self._highlight_button.setStyleSheet(
            "QToolButton { font-weight: 700; border: 1px solid #c7ccd1; "
            "border-radius: 3px; background: #fff6bf; }"
            "QToolButton:hover { border-color: #6aa9e9; }"
        )

        menu = QMenu(self._highlight_button)
        for label, latex_color, css_color in self._HIGHLIGHT_COLORS:
            action = menu.addAction(label)
            action.setData(latex_color)
            action.setToolTip(latex_color)
            action.triggered.connect(
                lambda checked=False, color=latex_color, css=css_color:
                self._choose_highlight(color, css)
            )
        self._highlight_button.setMenu(menu)

        self._apply_button = QToolButton(self)
        self._apply_button.setText("Apply")
        self._apply_button.setToolTip(
            "Save and apply settings.yaml"
        )
        self._apply_button.setFixedHeight(30)
        self._apply_button.setMinimumWidth(72)
        self._apply_button.setStyleSheet(
            "QToolButton { font-weight: 600; border: 1px solid #6aa9e9; "
            "border-radius: 3px; background: #eef5ff; padding: 0 10px; }"
            "QToolButton:hover { background: #dcecff; }"
        )
        self._apply_button.clicked.connect(
            self.apply_settings_requested.emit
        )
        self._apply_button.hide()

        layout.addWidget(self._bold_button)
        layout.addWidget(self._highlight_button)
        layout.addWidget(self._apply_button)
        layout.addStretch(1)

    def set_enabled_for_latex(self, enabled: bool) -> None:
        self._bold_button.setEnabled(bool(enabled))
        self._highlight_button.setEnabled(bool(enabled))

    def set_mode(
        self,
        *,
        latex_enabled: bool,
        settings_enabled: bool,
    ) -> None:
        self.set_enabled_for_latex(latex_enabled)
        self._bold_button.setVisible(bool(latex_enabled))
        self._highlight_button.setVisible(bool(latex_enabled))
        self._apply_button.setVisible(bool(settings_enabled))

    def _choose_highlight(self, latex_color: str, css_color: str) -> None:
        self._highlight_button.setStyleSheet(
            "QToolButton { font-weight: 700; border: 1px solid #c7ccd1; "
            f"border-radius: 3px; background: {css_color}; }}"
            "QToolButton:hover { border-color: #6aa9e9; }"
        )
        self.highlight_requested.emit(latex_color)
