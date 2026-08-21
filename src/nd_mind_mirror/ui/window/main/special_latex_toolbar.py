"""Provide compact LaTeX insertion controls shared by Source and Visual modes."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QToolButton, QWidget


class SpecialLatexToolbar(QWidget):
    """Expose a character palette and a one-click LaTeX iffalse wrapper action."""

    character_requested = Signal(str)
    iffalse_requested = Signal()

    _CHARACTER_GROUPS = {
        "Latin accents": ("é", "è", "ê", "ë", "á", "à", "â", "ä", "í", "ì", "î", "ï", "ó", "ò", "ô", "ö", "ú", "ù", "û", "ü"),
        "German / European": ("ß", "Ä", "Ö", "Ü", "ñ", "ç", "æ", "œ", "ø", "å"),
        "Math / typography": ("±", "×", "÷", "≤", "≥", "≠", "≈", "°", "–", "—", "…"),
    }

    def __init__(self, parent=None) -> None:
        """Build the compact toolbar and its character popup menus."""
        super().__init__(parent)
        self._character_button = QToolButton(self)
        self._character_button.setText("é…")
        self._character_button.setToolTip("Insert an unfamiliar Unicode character")
        self._character_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._character_button.setMenu(self._build_character_menu())

        self._iffalse_button = QPushButton(r"\iffalse … \fi", self)
        self._iffalse_button.setToolTip(
            r"Wrap the selection in \iffalse ... \fi; without a selection insert \iffalse Dativ plural\fi"
        )
        self._iffalse_button.clicked.connect(self.iffalse_requested.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self._character_button)
        layout.addWidget(self._iffalse_button)
        layout.addStretch(1)

    def _build_character_menu(self) -> QMenu:
        """Create grouped popup menus whose actions emit the chosen character."""
        menu = QMenu(self)
        for title, characters in self._CHARACTER_GROUPS.items():
            group = menu.addMenu(title)
            for character in characters:
                action = group.addAction(character)
                action.triggered.connect(
                    lambda checked=False, value=character: self.character_requested.emit(value)
                )
        return menu
