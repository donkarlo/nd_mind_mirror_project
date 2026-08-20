from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
)


class LatexFormatToolbar(QWidget):
    """Formatting and Source/Visual mode controls for the active LaTeX tab."""

    bold_requested = Signal()
    italic_requested = Signal()
    text_color_requested = Signal(str, str)
    highlight_requested = Signal(str, str)
    heading_requested = Signal(str)
    list_requested = Signal(str)
    edit_mode_requested = Signal(str)
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
    _TEXT_COLORS = (
        ("Black", "black", "#101828"),
        ("Red", "red", "#b42318"),
        ("Blue", "blue", "#175cd3"),
        ("Green", "green", "#067647"),
        ("Orange", "orange", "#b54708"),
        ("Violet", "violet", "#6938ef"),
        ("Cyan", "cyan", "#087e8b"),
        ("Gray", "gray", "#667085"),
    )
    _HEADINGS = (
        ("Part", "part"),
        ("Chapter", "chapter"),
        ("Section", "section"),
        ("Subsection", "subsection"),
        ("Subsubsection", "subsubsection"),
        ("Paragraph", "paragraph"),
        ("Subparagraph", "subparagraph"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._source_button = self._mode_button("Source")
        self._visual_button = self._mode_button("Visual")
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._source_button)
        self._mode_group.addButton(self._visual_button)
        self._source_button.setChecked(True)
        self._source_button.clicked.connect(
            lambda checked=False: self.edit_mode_requested.emit("source")
        )
        self._visual_button.clicked.connect(
            lambda checked=False: self.edit_mode_requested.emit("visual")
        )

        self._heading_button = QToolButton(self)
        self._heading_button.setText("Heading ▾")
        self._heading_button.setToolTip("Part / chapter / section hierarchy")
        self._heading_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        heading_menu = QMenu(self._heading_button)
        for label, command in self._HEADINGS:
            action = heading_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, value=command: self.heading_requested.emit(value)
            )
        self._heading_button.setMenu(heading_menu)

        self._bold_button = self._square_button("B", "Bold selection (Ctrl+B)")
        self._bold_button.setStyleSheet(self._button_style("font-weight: 700;"))
        self._bold_button.clicked.connect(self.bold_requested.emit)

        self._italic_button = self._square_button("I", "Italic selection")
        self._italic_button.setStyleSheet(self._button_style("font-style: italic;"))
        self._italic_button.clicked.connect(self.italic_requested.emit)

        self._text_color_button = self._square_button("A", "Text color")
        self._text_color_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        color_menu = QMenu(self._text_color_button)
        for label, latex_color, css_color in self._TEXT_COLORS:
            action = color_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, value=latex_color, css=css_color:
                self._choose_text_color(value, css)
            )
        self._text_color_button.setMenu(color_menu)

        self._highlight_button = self._square_button("H", "Highlight selected text")
        self._highlight_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._highlight_button.setStyleSheet(self._button_style("font-weight: 700;", "#fff6bf"))
        highlight_menu = QMenu(self._highlight_button)
        for label, latex_color, css_color in self._HIGHLIGHT_COLORS:
            action = highlight_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, color=latex_color, css=css_color:
                self._choose_highlight(color, css)
            )
        self._highlight_button.setMenu(highlight_menu)

        self._bullet_button = self._square_button("•", "Bulleted list (itemize)")
        self._bullet_button.clicked.connect(lambda checked=False: self.list_requested.emit("itemize"))
        self._number_button = self._square_button("1.", "Numbered list (enumerate)")
        self._number_button.clicked.connect(lambda checked=False: self.list_requested.emit("enumerate"))

        self._apply_button = QToolButton(self)
        self._apply_button.setText("Apply")
        self._apply_button.setToolTip("Save and apply settings.yaml")
        self._apply_button.setFixedHeight(30)
        self._apply_button.setMinimumWidth(72)
        self._apply_button.setStyleSheet(
            "QToolButton { font-weight: 600; border: 1px solid #6aa9e9; "
            "border-radius: 3px; background: #eef5ff; padding: 0 10px; }"
            "QToolButton:hover { background: #dcecff; }"
        )
        self._apply_button.clicked.connect(self.apply_settings_requested.emit)
        self._apply_button.hide()

        for widget in (
            self._source_button,
            self._visual_button,
            self._heading_button,
            self._bold_button,
            self._italic_button,
            self._text_color_button,
            self._highlight_button,
            self._bullet_button,
            self._number_button,
            self._apply_button,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)

        self.set_mode(latex_enabled=False, settings_enabled=False)

    def set_edit_mode(self, mode: str) -> None:
        visual = str(mode).strip().lower() == "visual"
        self._visual_button.setChecked(visual)
        self._source_button.setChecked(not visual)
        self._refresh_visibility()

    def set_enabled_for_latex(self, enabled: bool) -> None:
        for button in self._latex_buttons():
            button.setEnabled(bool(enabled))

    def set_mode(self, *, latex_enabled: bool, settings_enabled: bool) -> None:
        self._latex_enabled = bool(latex_enabled)
        self._settings_enabled = bool(settings_enabled)
        self.set_enabled_for_latex(self._latex_enabled)
        self._refresh_visibility()

    def _refresh_visibility(self) -> None:
        latex_enabled = bool(getattr(self, "_latex_enabled", False))
        settings_enabled = bool(getattr(self, "_settings_enabled", False))
        visual = self._visual_button.isChecked()

        # The Source/Visual mode switch must remain visible for every LaTeX
        # tab. Formatting controls belong to the graphical editor only and
        # are intentionally hidden while Source mode is active.
        self._source_button.setVisible(latex_enabled)
        self._visual_button.setVisible(latex_enabled)
        for button in self._visual_only_buttons():
            button.setVisible(latex_enabled and visual)
        self._apply_button.setVisible(settings_enabled)

    def _visual_only_buttons(self) -> tuple[QToolButton, ...]:
        return (
            self._heading_button,
            self._bold_button,
            self._italic_button,
            self._text_color_button,
            self._highlight_button,
            self._bullet_button,
            self._number_button,
        )

    def _latex_buttons(self) -> tuple[QToolButton, ...]:
        return (
            self._source_button,
            self._visual_button,
            *self._visual_only_buttons(),
        )

    def _choose_highlight(self, latex_color: str, css_color: str) -> None:
        self._highlight_button.setStyleSheet(
            self._button_style("font-weight: 700;", css_color)
        )
        self.highlight_requested.emit(latex_color, css_color)

    def _choose_text_color(self, latex_color: str, css_color: str) -> None:
        self._text_color_button.setStyleSheet(
            self._button_style(f"font-weight: 700; color: {css_color};")
        )
        self.text_color_requested.emit(latex_color, css_color)

    def _mode_button(self, text: str) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setCheckable(True)
        button.setFixedHeight(30)
        button.setMinimumWidth(62)
        button.setStyleSheet(
            "QToolButton { border: 1px solid #c7ccd1; border-radius: 3px; "
            "background: white; padding: 0 8px; }"
            "QToolButton:checked { background: #dcecff; border-color: #6aa9e9; "
            "font-weight: 600; }"
        )
        return button

    def _square_button(self, text: str, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(30, 30)
        button.setStyleSheet(self._button_style())
        return button

    @staticmethod
    def _button_style(extra: str = "", background: str = "#ffffff") -> str:
        return (
            "QToolButton { " + extra + " border: 1px solid #c7ccd1; "
            f"border-radius: 3px; background: {background}; }}"
            "QToolButton:hover { background: #eef5ff; border-color: #6aa9e9; }"
        )
