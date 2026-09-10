from nd_mind_mirror.ui.window.main.bookmark_selection_menu_controller import (
    BookmarkSelectionMenuController,
)
from nd_mind_mirror.ui.window.main.enhanced_main_window_base import (
    EnhancedMainWindow as BaseEnhancedMainWindow,
)
from nd_mind_mirror.ui.window.main.preview.profile.latex_preview_profile_controller import (
    LatexPreviewProfileController,
)


class EnhancedMainWindow(BaseEnhancedMainWindow):
    """Compose the enhanced window with bookmark and profile-aware Preview controllers."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bookmark_selection_menu_controller = BookmarkSelectionMenuController(
            self._editor_panel,
            self._bookmarks_menu,
            self._toggle_bookmark_action,
            self,
        )
        self._latex_preview_profile_controller = LatexPreviewProfileController(
            self
        )

    def _reload_yaml_settings(self) -> bool:
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
