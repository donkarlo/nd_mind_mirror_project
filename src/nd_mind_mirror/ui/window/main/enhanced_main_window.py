"""Layer focused UX enhancements over the current MainWindow without replacing its large implementation."""

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from nd_mind_mirror.ui.window.main.main_window import MainWindow
from nd_mind_mirror.ui.window.main.latex_insertion_controller import LatexInsertionController
from nd_mind_mirror.ui.window.main.navigator_context_controller import NavigatorContextController
from nd_mind_mirror.ui.window.main.pinned_tab_controller import PinnedTabController
from nd_mind_mirror.ui.window.main.preview_auto_fit_controller import PreviewAutoFitController
from nd_mind_mirror.ui.window.main.preview_toggle_button_controller import PreviewToggleButtonController
from nd_mind_mirror.ui.window.main.shortcut_settings_dialog import ShortcutSettingsDialog
from nd_mind_mirror.ui.window.main.shortcut_store import ShortcutStore
from nd_mind_mirror.ui.window.main.special_latex_toolbar import SpecialLatexToolbar
from nd_mind_mirror.ui.window.main.structure_highlight_controller import StructureHighlightController
from nd_mind_mirror.ui.window.main.tree_state_toggle_controller import TreeStateToggleController
from nd_mind_mirror.ui.window.main.undo_redo_controller import UndoRedoController


class EnhancedMainWindow(MainWindow):
    """Compose the requested navigator, editor, preview, pinning, and shortcut enhancements."""

    def __init__(self, parent=None) -> None:
        """Initialize the existing window first, then attach additive controllers to its stable widgets."""
        super().__init__(parent)
        self._undo_redo_controller = UndoRedoController(self)
        self._preview_toggle_button_controller = PreviewToggleButtonController(
            self,
            self._show_preview_action,
            self,
        )
        self._install_latex_insert_toolbar()
        self._structure_highlight_controller = StructureHighlightController(self._structure_panel)
        self._navigator_tree_state = TreeStateToggleController(
            self._file_system_panel,
            self._file_system_panel._tree,
            self._file_system_panel._label,
            self._file_system_panel,
        )
        self._structure_tree_state = TreeStateToggleController(
            self._structure_panel,
            self._structure_panel._tree,
            self._structure_panel._label,
            self._structure_panel,
        )
        self._pinned_tab_controller = PinnedTabController(
            self._editor_panel,
            self._session_settings,
            lambda path: self._open_path(str(path), select=False),
        )
        self._file_system_panel.path_renamed.connect(self._pinned_tab_controller.rename_path)
        self._file_system_panel.path_deleted.connect(self._pinned_tab_controller.remove_deleted_path)
        self._navigator_context_controller = NavigatorContextController(
            self._file_system_panel,
            pin_callback=self._pin_navigator_path,
        )
        self._preview_auto_fit_controller = PreviewAutoFitController(
            self._preview_panel,
            self._splitter,
            self._session_settings,
            self,
        )
        self._install_shortcut_settings()

    def _install_latex_insert_toolbar(self) -> None:
        """Add the unfamiliar-character popup and iffalse button above every LaTeX Source/Visual tab."""
        self._special_latex_toolbar = SpecialLatexToolbar(self._editor_panel)
        self._latex_insertion_controller = LatexInsertionController(self._editor_panel, self)
        self._special_latex_toolbar.character_requested.connect(
            self._latex_insertion_controller.insert_character
        )
        self._special_latex_toolbar.iffalse_requested.connect(
            self._latex_insertion_controller.insert_iffalse
        )
        self._editor_panel.panel_layout.insertWidget(2, self._special_latex_toolbar)
        self._editor_panel.current_document_changed.connect(
            lambda path, _content: self._update_special_toolbar_visibility(path)
        )
        current = self._editor_panel.current_path()
        self._update_special_toolbar_visibility(str(current) if current is not None else "")

    def _update_special_toolbar_visibility(self, path: str) -> None:
        """Show special LaTeX controls only for tex/tikz documents where both edit modes exist."""
        suffix = Path(path).suffix.lower() if path else ""
        self._special_latex_toolbar.setVisible(suffix in {".tex", ".tikz"})

    def _pin_navigator_path(self, path: Path) -> None:
        """Open a Navigator file if necessary and add it to the persistent pinned tab group."""
        self._pinned_tab_controller.pin_path(path)

    def _install_shortcut_settings(self) -> None:
        """Create the shortcut store and attach its Apply-based editor to a persistent Settings menu."""
        defaults = (
            self._app_settings.project_root
            / "src"
            / "nd_mind_mirror"
            / "core"
            / "settings"
            / "defaults"
            / "keyboard_shortcuts.yaml"
        )
        self._shortcut_store = ShortcutStore(self._app_settings.data_root, defaults)
        self._keyboard_shortcuts_action = QAction("Keyboard Shortcuts…", self)
        self._keyboard_shortcuts_action.triggered.connect(self._show_keyboard_shortcuts)
        settings_menu = self._rebuild_settings_menu()
        settings_menu.addSeparator()
        settings_menu.addAction(self._keyboard_shortcuts_action)
        self._apply_keyboard_shortcuts()

    def _rebuild_settings_menu(self) -> QMenu:
        """Replace the base temporary Settings menu with a Python-owned menu that stays alive."""
        menu_bar = self.menuBar()
        for action in list(menu_bar.actions()):
            if action.text().replace("&", "") == "Settings":
                menu_bar.removeAction(action)

        self._settings_menu_ref = QMenu("Settings", self)
        menu_bar.addMenu(self._settings_menu_ref)
        self._settings_menu_ref.addAction(self._edit_settings_action)
        self._settings_menu_ref.addAction(self._edit_latex_shortcuts_action)
        self._settings_menu_ref.addAction(self._edit_preview_template_action)
        self._settings_menu_ref.addAction(self._edit_beamer_preview_template_action)
        self._settings_menu_ref.addAction(self._reload_settings_action)
        return self._settings_menu_ref

    def _show_keyboard_shortcuts(self) -> None:
        """Open the shortcut table whose Apply button writes YAML and updates live QAction/QShortcut objects."""
        dialog = ShortcutSettingsDialog(
            self._shortcut_store,
            self._apply_keyboard_shortcuts,
            self,
        )
        dialog.exec()

    def _apply_keyboard_shortcuts(self) -> None:
        """Reload keyboard_shortcuts.yaml and apply its configured sequences to all exposed application actions."""
        self._shortcut_store.reload()
        bindings = {
            "file.open": self._open_action,
            "file.save": self._save_action,
            "tab.close": self._close_tab_action,
            "latex.format": self._format_action,
            "find.current": self._find_in_tab_action,
            "replace.current": self._replace_in_tab_action,
            "bookmark.toggle": self._toggle_bookmark_action,
            "preview.toggle": self._show_preview_action,
            "editor.bold": self._editor_panel._bold_shortcut,
            "editor.reset_zoom": self._editor_panel._reset_zoom_shortcut,
            "find.close": self._editor_panel._find_escape_shortcut,
            "navigator.delete": self._file_system_panel._delete_shortcut,
        }
        self._shortcut_store.apply(bindings)
        self.statusBar().showMessage(
            f"Keyboard shortcuts applied from {self._shortcut_store.path}", 3500
        )

    def _settings_menu(self):
        """Return the persistent Settings menu created by the enhanced window."""
        return getattr(self, "_settings_menu_ref", None)
