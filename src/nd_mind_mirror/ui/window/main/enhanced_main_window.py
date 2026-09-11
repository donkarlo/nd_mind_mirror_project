"""Compose the final enhanced window with scoped workspace search integration."""

from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.ui.window.main.bookmark_selection_menu_controller import (
    BookmarkSelectionMenuController,
)
from nd_mind_mirror.ui.window.main.enhanced_main_window_base import (
    EnhancedMainWindow as BaseEnhancedMainWindow,
)
from nd_mind_mirror.ui.window.main.preview.profile.latex_preview_profile_controller import (
    LatexPreviewProfileController,
)
from nd_mind_mirror.ui.window.main.search_aware_navigator_multi_path_context_controller import (
    SearchAwareNavigatorMultiPathContextController,
)


class EnhancedMainWindow(BaseEnhancedMainWindow):
    """Compose the enhanced window with search-aware Navigator and Preview controllers."""

    def __init__(self, parent=None) -> None:
        """Initialize final window controllers and text-result navigation."""
        super().__init__(parent)
        self._search_window.text_location_selected.connect(
            self._open_search_text_location
        )
        self._bookmark_selection_menu_controller = BookmarkSelectionMenuController(
            self._editor_panel,
            self._bookmarks_menu,
            self._toggle_bookmark_action,
            self,
        )
        self._latex_preview_profile_controller = LatexPreviewProfileController(self)

    def _replace_navigator_context_controller(self) -> None:
        """Install one canonical multi-path menu with folder-scoped search actions."""
        existing = getattr(self, "_navigator_context_controller", None)
        self._navigator_context_controller = (
            SearchAwareNavigatorMultiPathContextController.replace(
                existing,
                self._file_system_panel,
                pin_callback=self._pin_navigator_path,
                file_search_callback=self._show_file_search_from_navigator,
                text_search_callback=self._show_text_search_from_navigator,
            )
        )

    def _show_file_search_from_navigator(self, path: Path) -> None:
        """Open file/folder search scoped to a Navigator folder."""
        self._search_window.show_file_search(path)

    def _show_text_search_from_navigator(self, path: Path) -> None:
        """Open text search scoped to a Navigator folder."""
        self._search_window.show_text_search(path)

    def _open_search_text_location(
        self,
        path: str,
        line: int,
        column: int,
    ) -> None:
        """Open a text-search hit and place the Source cursor on that occurrence."""
        source_path = Path(path).expanduser().resolve(strict=False)
        if not source_path.is_file():
            self.statusBar().showMessage(
                f"Search result no longer exists: {source_path}",
                5000,
            )
            return

        self._open_path(str(source_path))
        QTimer.singleShot(
            0,
            lambda: self._editor_panel.go_to_location(
                max(int(line), 1),
                max(int(column), 1),
            ),
        )

    def _reload_yaml_settings(self) -> bool:
        """Reload settings and refresh the Preview profile controller."""
        loaded = super()._reload_yaml_settings()
        if not loaded:
            return False
        controller = getattr(
            self,
            "_latex_preview_profile_controller",
            None,
        )
        if controller is not None:
            controller.reload_settings(refresh=True)
        return True
