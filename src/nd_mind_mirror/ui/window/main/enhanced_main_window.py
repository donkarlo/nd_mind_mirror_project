"""Compose the final enhanced window with scoped search and live TikZ integration."""

from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.ui.editor.latex.source_latex_preview_controller import (
    SourceLatexPreviewController,
)
from nd_mind_mirror.ui.editor.latex.source_tikz_targeted_preview_controller import (
    SourceTikZTargetedPreviewController,
)
from nd_mind_mirror.ui.window.main.autosave.existing_file_document_autosave_controller import (
    ExistingFileDocumentAutosaveController,
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
from nd_mind_mirror.ui.window.main.structure_source_rewrite_controller import (
    StructureSourceRewriteController,
)
from nd_mind_mirror.ui.window.main.tikz.tikz_live_refresh_controller import (
    TikZLiveRefreshController,
)
from nd_mind_mirror.ui.window.main.tikz_update_event_controller import (
    TikZUpdateEventController,
)


class EnhancedMainWindow(BaseEnhancedMainWindow):
    """Compose search-aware desktop features over the shared image/TikZ bridge."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._externally_missing_paths: set[Path] = set()
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
        self._structure_source_rewrite_controller = StructureSourceRewriteController(
            self._structure_panel,
            self._editor_panel,
            self,
            self,
        )
        self._latex_preview_profile_controller = LatexPreviewProfileController(self)
        self._source_latex_preview_controller = SourceLatexPreviewController(
            self._editor_panel,
            self,
        )
        self._source_tikz_preview_controller = SourceTikZTargetedPreviewController(
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

        self._tikz_live_refresh_controller = TikZLiveRefreshController(
            self,
            live_interval_ms=50,
            pdf_idle_delay_ms=1200,
        )
        self._tikz_live_refresh_controller.live_refresh_requested.connect(
            self._refresh_tikz_live_projections
        )
        self._tikz_live_refresh_controller.pdf_refresh_requested.connect(
            self._refresh_tikz_pdf_projection
        )

        QTimer.singleShot(
            0,
            lambda: self._refresh_current_preview(immediate=True),
        )

    def _replace_document_autosave_controller(self) -> None:
        """Use deletion-safe local-cache autosave for the final window."""
        existing = getattr(self, "_document_autosave_controller", None)
        if existing is not None:
            existing.shutdown()
        self._document_autosave_controller = ExistingFileDocumentAutosaveController(
            self._editor_panel,
            protected_path=self._app_settings.latex_shortcuts_file_path,
            on_written=self._remember_autosave_write,
            parent=self,
        )

    def _sync_external_file_changes(self) -> None:
        """Refresh Navigator when an open canonical file disappears externally."""
        filesystem = getattr(
            self,
            "_workspace_filesystem_operation_controller",
            None,
        )
        references = getattr(
            self,
            "_workspace_reference_maintenance_controller",
            None,
        )
        if (
            (filesystem is not None and filesystem.has_pending_work)
            or (references is not None and references.has_pending_work)
        ):
            super()._sync_external_file_changes()
            return

        missing = {
            Path(path).expanduser().resolve(strict=False)
            for path in self._editor_panel.open_paths()
            if not Path(path).expanduser().resolve(strict=False).is_file()
        }
        newly_missing = missing - self._externally_missing_paths
        self._externally_missing_paths = missing
        if newly_missing:
            for path in newly_missing:
                self._file_signatures.pop(path, None)
            refresh = getattr(
                self,
                "_navigator_filesystem_model_refresh_controller",
                None,
            )
            if refresh is not None:
                current = self._editor_panel.current_path()
                current_path = (
                    Path(current).expanduser().resolve(strict=False)
                    if current is not None
                    else None
                )
                selected = (
                    current_path.parent
                    if current_path is not None and current_path in missing
                    else None
                )
                refresh.refresh(selected)
            self.statusBar().showMessage(
                "A file open in the editor was deleted outside Mind Mirror; autosave will not recreate it.",
                5000,
            )

        super()._sync_external_file_changes()

    def _on_tikz_source_updated(self, path: str) -> None:
        """Reload Source now; live graphics and PDF follow separate bounded schedules."""
        source_path = self._resolve_tikz_event_path(path)
        self._reload_open_tikz_source(source_path)
        self._tikz_live_refresh_controller.submit(source_path)

    def _refresh_tikz_live_projections(self, paths: object) -> None:
        """Refresh only Source/Visual projections that depend on changed TikZ files."""
        if not isinstance(paths, tuple):
            return

        editor = self._editor_panel.current_editor()
        visual_refresh = getattr(editor, "refresh_visual_tikz_path", None)
        for source_path in paths:
            self._source_tikz_preview_controller.notify_tikz_changed(
                source_path
            )
            if callable(visual_refresh):
                visual_refresh(source_path)

    def _refresh_tikz_pdf_projection(self) -> None:
        """Compile the full PDF only after the external TikZ edit stream is idle."""
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
