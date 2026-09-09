"""Provide compact LaTeX insertion controls only while Source is active."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMenu, QPushButton, QToolButton, QWidget

from nd_mind_mirror.ui.editor.bookmark.bookmark_lifecycle_controller import (
    BookmarkLifecycleController,
)
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_graphic_preview_controller import (
    SourceGraphicPreviewController,
)
from nd_mind_mirror.ui.editor.latex.visual_graphic_context_controller import (
    VisualGraphicContextController,
)
from nd_mind_mirror.ui.search.search_typing_controller import SearchTypingController
from nd_mind_mirror.ui.window.main.bookmark_selection_menu_controller import (
    BookmarkSelectionMenuController,
)
from nd_mind_mirror.ui.window.main.fix11_desktop_controller import Fix11DesktopController
from nd_mind_mirror.ui.window.main.source_edit_command_controller import (
    SourceEditCommandController,
)

Fix11DesktopController.install()


class SpecialLatexToolbar(QWidget):
    """Expose Source-only LaTeX insertion controls and shared UI controllers."""

    character_requested = Signal(str)
    iffalse_requested = Signal()

    _CHARACTER_GROUPS = {
        "Latin accents": ("é", "è", "ê", "ë", "á", "à", "â", "ä", "í", "ì", "î", "ï", "ó", "ò", "ô", "ö", "ú", "ù", "û", "ü"),
        "German / European": ("ß", "Ä", "Ö", "Ü", "ñ", "ç", "æ", "œ", "ø", "å"),
        "Math / typography": ("±", "×", "÷", "≤", "≥", "≠", "≈", "°", "–", "—", "…"),
    }

    def __init__(self, parent=None) -> None:
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

        self._escape_underscore_button = QPushButton(r"_ → \_", self)
        self._escape_underscore_button.setToolTip(
            r"Convert unescaped underscores in the current Source selection to \_"
        )
        self._source_edit_command_controller = SourceEditCommandController(parent, self)
        self._escape_underscore_button.clicked.connect(
            self._source_edit_command_controller.escape_selected_underscores
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self._character_button)
        layout.addWidget(self._iffalse_button)
        layout.addWidget(self._escape_underscore_button)
        layout.addStretch(1)

        self._source_graphic_preview_controller = None
        self._visual_graphic_context_controller = None
        self._bookmark_lifecycle_controller = None
        self._bookmark_selection_menu_controller = None
        self._search_typing_controller = None
        if parent is not None:
            parent.current_view_changed.connect(
                lambda *_args: self.setVisible(True)
            )
            self._source_graphic_preview_controller = SourceGraphicPreviewController(
                parent,
                self,
            )
            self._visual_graphic_context_controller = VisualGraphicContextController(
                parent,
                self,
            )
            window = parent.window()
            file_system_panel = getattr(window, "_file_system_panel", None)
            if file_system_panel is not None:
                self._bookmark_lifecycle_controller = BookmarkLifecycleController(
                    parent,
                    file_system_panel,
                    self,
                )
            bookmarks_menu = getattr(window, "_bookmarks_menu", None)
            if bookmarks_menu is not None:
                self._bookmark_selection_menu_controller = (
                    BookmarkSelectionMenuController(
                        parent,
                        bookmarks_menu,
                        self,
                    )
                )
            search_window = getattr(window, "_search_window", None)
            if search_window is not None:
                self._search_typing_controller = SearchTypingController(
                    search_window,
                    self,
                )

    def setVisible(self, visible: bool) -> None:
        """Never expose the Source-special toolbar while Visual is active."""
        if visible:
            editor_panel = self.parent()
            current_editor = (
                editor_panel.current_editor()
                if editor_panel is not None
                and hasattr(editor_panel, "current_editor")
                else None
            )
            visible = (
                isinstance(current_editor, LatexEditor)
                and current_editor.edit_mode == "source"
            )
        super().setVisible(bool(visible))

    def _build_character_menu(self) -> QMenu:
        menu = QMenu(self)
        for title, characters in self._CHARACTER_GROUPS.items():
            group = menu.addMenu(title)
            for character in characters:
                action = group.addAction(character)
                action.triggered.connect(
                    lambda checked=False, value=character: self.character_requested.emit(value)
                )
        return menu
