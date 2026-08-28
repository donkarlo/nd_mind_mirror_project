"""Layer focused UX enhancements over the current MainWindow without replacing its large implementation."""

from pathlib import Path
import re

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QMenu

from nd_mind_mirror.ui.window.main.main_window import MainWindow
from nd_mind_mirror.ui.window.main.latex_insertion_controller import LatexInsertionController
from nd_mind_mirror.ui.window.main.navigator_context_controller import NavigatorContextController
from nd_mind_mirror.ui.window.main.pinned_tab_controller import PinnedTabController
from nd_mind_mirror.ui.window.main.preview_auto_fit_controller import PreviewAutoFitController
from nd_mind_mirror.ui.window.main.preview_reverse_sync_controller import (
    PreviewReverseSyncController,
)
from nd_mind_mirror.ui.window.main.preview_toggle_button_controller import PreviewToggleButtonController
from nd_mind_mirror.ui.window.main.shortcut_settings_dialog import ShortcutSettingsDialog
from nd_mind_mirror.ui.window.main.shortcut_store import ShortcutStore
from nd_mind_mirror.ui.window.main.special_latex_toolbar import SpecialLatexToolbar
from nd_mind_mirror.ui.window.main.structure_highlight_controller import StructureHighlightController
from nd_mind_mirror.ui.window.main.tree_state_toggle_controller import TreeStateToggleController
from nd_mind_mirror.ui.window.main.undo_redo_controller import UndoRedoController
from nd_mind_mirror.ui.window.main.visual_persian_font_controller import (
    VisualPersianFontController,
)
from nd_mind_mirror.ui.window.main.visual_window_controller import VisualWindowController


class EnhancedMainWindow(MainWindow):
    """Compose the requested navigator, editor, preview, pinning, and shortcut enhancements."""

    _ABSOLUTE_INPUT_PATTERN = re.compile(
        r"\\(?:input|include)\s*\{(?P<path>/[^{}]+)\}"
    )
    _SMALL_PREVIEW_SOURCE_CHARS = 60_000

    def __init__(self, parent=None) -> None:
        """Initialize the existing window first, then attach additive controllers to its stable widgets."""
        super().__init__(parent)
        self._install_preview_render_recovery()
        self._visual_window_controller = VisualWindowController(
            self._editor_panel,
            self,
        )
        self._visual_persian_font_controller = VisualPersianFontController(
            self._editor_panel,
            self._app_settings,
            self,
        )
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
        self._preview_reverse_sync_controller = PreviewReverseSyncController(
            self,
            self,
        )
        self._install_navigator_rename_shortcut()
        self._install_shortcut_settings()
        self._sync_auto_format_action(self._editor_panel.current_path())

    def _install_preview_render_recovery(self) -> None:
        """Keep small-file Preview live and fail immediately on missing absolute inputs."""
        renderer = self._renderer
        base_compile_pending_source = renderer._compile_pending_source
        base_render = renderer.render
        last_render_path: Path | None = None

        # ND_MIGRATION4_IMMEDIATE_SMALL_OPEN
        # A newly opened small source should start compiling immediately. The
        # normal typing debounce remains in force for subsequent keystrokes.
        def render_source(
            source: str,
            source_path=None,
            immediate: bool = False,
        ) -> None:
            nonlocal last_render_path
            resolved = None
            if source_path is not None:
                try:
                    resolved = Path(source_path).expanduser().resolve()
                except (OSError, TypeError, ValueError):
                    resolved = None
            first_small_open = (
                len(source) < self._SMALL_PREVIEW_SOURCE_CHARS
                and resolved is not None
                and resolved != last_render_path
            )
            if resolved is not None:
                last_render_path = resolved
            base_render(
                source,
                source_path=source_path,
                immediate=bool(immediate or first_small_open),
            )

        def compile_pending_source() -> None:
            source = str(getattr(renderer, "_pending_source", "") or "")
            for match in self._ABSOLUTE_INPUT_PATTERN.finditer(source):
                raw_path = match.group("path").strip()
                candidate = Path(raw_path).expanduser()
                options = [candidate]
                if not candidate.suffix:
                    options.append(candidate.with_suffix(".tex"))
                if not any(option.is_file() for option in options):
                    renderer.failed.emit(f"Missing LaTeX input: {raw_path}")
                    return

            # ND_FAST_PREVIEW_COALESCE
            # Never kill a healthy small-file compile because another startup
            # signal arrived. The renderer already coalesces queued generations
            # and starts only the newest one when the active process finishes.
            base_compile_pending_source()

        renderer.render = render_source
        renderer._compile_pending_source = compile_pending_source
        try:
            renderer._timer.timeout.disconnect()
        except (RuntimeError, TypeError):
            pass
        renderer._timer.timeout.connect(compile_pending_source)
        self._nd_preview_compile_pending_source = compile_pending_source

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

    def _on_current_document_changed(self, path: str, content: str) -> None:
        """Keep the base document-change behavior and expose Auto Format for YAML."""
        super()._on_current_document_changed(path, content)
        self._sync_auto_format_action(path)

    def _sync_auto_format_action(self, path: str | Path | None) -> None:
        """Enable the shared Auto Format action for LaTeX and YAML editors."""
        self._format_action.setText("Auto Format")
        suffix = Path(path).suffix.lower() if path else ""
        self._format_action.setEnabled(
            suffix in {".tex", ".tikz", ".yaml", ".yml"}
        )

    def _pin_navigator_path(self, path: Path) -> None:
        """Open a Navigator file if necessary and add it to the persistent pinned tab group."""
        self._pinned_tab_controller.pin_path(path)

    def _install_navigator_rename_shortcut(self) -> None:
        """Bind F2 to the Navigator's existing file/folder rename workflow."""
        self._navigator_rename_shortcut = QShortcut(
            QKeySequence("F2"),
            self._file_system_panel._tree,
        )
        self._navigator_rename_shortcut.setContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self._navigator_rename_shortcut.activated.connect(
            self._rename_navigator_selection
        )

    def _rename_navigator_selection(self) -> None:
        """Rename the selected Navigator file or folder unless it is the workspace root."""
        selected = self._file_system_panel.selected_path()
        if not selected:
            return
        path = Path(selected).expanduser().resolve()
        root = self._file_system_panel._root_path
        if path == root or not path.exists():
            return
        self._file_system_panel._rename_path(path)

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

    def _reload_yaml_settings(self) -> bool:
        """Reload base settings and immediately refresh the Visual Persian font controller."""
        reloaded = super()._reload_yaml_settings()
        controller = getattr(self, "_visual_persian_font_controller", None)
        if reloaded and controller is not None:
            controller.reload()
        return reloaded

    def _settings_menu(self):
        """Return the persistent Settings menu created by the enhanced window."""
        return getattr(self, "_settings_menu_ref", None)
