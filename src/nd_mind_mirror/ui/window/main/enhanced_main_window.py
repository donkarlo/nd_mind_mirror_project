"""Compose the final enhanced window with scoped search and live TikZ integration."""

from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.ui.editor.latex.source_tikz_preview_controller import (
    SourceTikZPreviewController,
)
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
from nd_mind_mirror.ui.window.main.tikz_update_event_controller import (
    TikZUpdateEventController,
)


class EnhancedMainWindow(BaseEnhancedMainWindow):
    """Compose search-aware desktop features over the shared image/TikZ bridge."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        workspace_root = self._app_settings.search_default_path
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._renderer.set_workspace_default_path(workspace_root)
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
        self._source_tikz_preview_controller = SourceTikZPreviewController(
            self._editor_panel,
            workspace_root,
            self,
        )
        self._tikz_update_event_controller = TikZUpdateEventController(
            workspace_root,
            self,
        )
        self._tikz_update_event_controller.updated.connect(
            self._on_tikz_source_updated
        )
        QTimer.singleShot(
            0,
            lambda: self._refresh_current_preview(immediate=True),
        )

    def _on_tikz_source_updated(self, path: str) -> None:
        """Refresh Source, Visual, and PDF Preview from one low-latency TikZ event."""
        source_path = self._resolve_tikz_event_path(path)
        self._reload_open_tikz_source(source_path)
        self._source_tikz_preview_controller.notify_tikz_changed(
            str(source_path)
        )
        self._editor_panel.refresh_current_visual_graphics()
        if self._preview_enabled:
            self._refresh_current_preview(immediate=True)

    def _resolve_tikz_event_path(self, path: str | Path) -> Path:
        """Resolve the bridge's workspace-relative event path deterministically."""
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve(strict=False)
        return (self._workspace_root / candidate).resolve(strict=False)

    def _reload_open_tikz_source(self, source_path: Path) -> None:
        """Apply the canonical iPad save immediately to an already-open Source tab."""
        current_content = self._editor_panel.content_for_path(source_path)
        if current_content is None or not source_path.is_file():
            return
        try:
            disk_content = self._load_editor_file(source_path)
        except (OSError, ValueError):
            return
        if current_content != disk_content:
            self._editor_panel.replace_content_from_disk(
                source_path,
                disk_content,
            )
        self._remember_file_signature(source_path)

    def _replace_navigator_context_controller(self) -> None:
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
        self._search_window.show_file_search(path)

    def _show_text_search_from_navigator(self, path: Path) -> None:
        self._search_window.show_text_search(path)

    def _open_search_text_location(
        self,
        path: str,
        line: int,
        column: int,
    ) -> None:
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
        loaded = super()._reload_yaml_settings()
        if not loaded:
            return False
        self._workspace_root = Path(
            self._app_settings.search_default_path
        ).expanduser().resolve()
        self._renderer.set_workspace_default_path(
            self._app_settings.search_default_path
        )
        controller = getattr(
            self,
            "_latex_preview_profile_controller",
            None,
        )
        if controller is not None:
            controller.reload_settings(refresh=True)
        return True
