"""Compose enhanced window features with robust persistent-session handling."""

from pathlib import Path

from PySide6.QtCore import QTimer

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_builder import (
    LatexDiagnosticBuilder,
)
from nd_mind_mirror.core.settings.storage.session_string_list_sanitizer import (
    SessionStringListSanitizer,
)
from nd_mind_mirror.ui.window.main.autosave.low_sync_document_autosave_controller import (
    LowSyncDocumentAutosaveController,
)
from nd_mind_mirror.ui.window.main.enhanced_main_window_features import (
    EnhancedMainWindow as FeatureEnhancedMainWindow,
)
from nd_mind_mirror.ui.window.main.navigator_multi_path_context_controller import (
    NavigatorMultiPathContextController,
)
from nd_mind_mirror.ui.window.main.current_editor_tab_close_controller import (
    CurrentEditorTabCloseController,
)
from nd_mind_mirror.ui.window.main.navigator_strict_active_selection_controller import (
    NavigatorStrictActiveSelectionController,
)
from nd_mind_mirror.ui.window.main.navigator_filesystem_model_refresh_controller import (
    NavigatorFilesystemModelRefreshController,
)
from nd_mind_mirror.ui.window.main.workspace.reference_maintenance_controller import (
    WorkspaceReferenceMaintenanceController,
)
from nd_mind_mirror.ui.window.main.graphic_open_session_path_controller import (
    GraphicOpenSessionPathController,
)
from nd_mind_mirror.ui.window.main.workspace.managed_graphic_filesystem_operation_controller import (
    ManagedGraphicWorkspaceFilesystemOperationController,
)
from nd_mind_mirror.graphic.core.bridge_session_process_controller import (
    GraphicBridgeSessionProcessController,
)


class EnhancedMainWindow(FeatureEnhancedMainWindow):
    """Run the enhanced window with safe session state and non-blocking workspace operations."""

    _SESSION_STRING_LIST_KEYS = (
        "filesystem/expanded_paths",
        "editor/recent_files",
    )

    def __init__(self, parent=None) -> None:
        """Initialize enhanced features, Navigator clipboard, workers, and active-file navigation."""
        super().__init__(parent)
        self._latex_diagnostic_builder = LatexDiagnosticBuilder(
            default_path=self._app_settings.search_default_path,
            template_path=self._app_settings.preview_latex_template_path,
            beamer_template_path=self._app_settings.preview_latex_beamer_template_path,
        )
        self._preview_panel.source_location_requested.connect(
            self._open_latex_diagnostic_location
        )
        self._replace_document_autosave_controller()
        self._replace_navigator_context_controller()
        self._navigator_filesystem_model_refresh_controller = (
            NavigatorFilesystemModelRefreshController(
                self._file_system_panel,
                self,
            )
        )
        self._current_editor_tab_close_controller = (
            CurrentEditorTabCloseController(
                self,
                self._editor_panel,
                self._close_tab_action,
                self,
            )
        )
        self._graphic_bridge_session_process_controller = (
            GraphicBridgeSessionProcessController(
                workspace_root=self._app_settings.search_default_path,
                project_root=self._app_settings.project_root,
                parent=self,
            )
        )
        self._graphic_bridge_session_process_controller.start()
        self._refresh_current_preview(immediate=True)
        self._workspace_reference_maintenance_controller = (
            WorkspaceReferenceMaintenanceController(self, self)
        )
        self._workspace_filesystem_operation_controller = (
            ManagedGraphicWorkspaceFilesystemOperationController(self, self)
        )
        self._graphic_open_session_path_controller = GraphicOpenSessionPathController(
            self,
            self,
        )
        self._navigator_active_selection_controller = (
            NavigatorStrictActiveSelectionController(
                self._editor_panel,
                self._file_system_panel,
                self,
            )
        )

    def _replace_document_autosave_controller(self) -> None:
        """Use local cache staging so autosave creates no temporary files in Dropbox."""
        existing = getattr(self, "_document_autosave_controller", None)
        if existing is not None:
            existing.shutdown()
        self._document_autosave_controller = LowSyncDocumentAutosaveController(
            self._editor_panel,
            protected_path=self._app_settings.latex_shortcuts_file_path,
            on_written=self._remember_autosave_write,
            parent=self,
        )

    def _replace_navigator_context_controller(self) -> None:
        """Install Ctrl/Shift multi-selection Copy/Cut/Paste without duplicate shortcuts."""
        existing = getattr(self, "_navigator_context_controller", None)
        self._navigator_context_controller = NavigatorMultiPathContextController.replace(
            existing,
            self._file_system_panel,
            pin_callback=self._pin_navigator_path,
        )

    def _configure_workspace_input_resolver(self) -> None:
        """Use search.default_path for Preview input/include and graphic resolution."""
        renderer = getattr(self, "_renderer", None)
        settings = getattr(self, "_app_settings", None)
        if renderer is None or settings is None:
            return
        renderer.set_workspace_default_path(
            settings.search_default_path
        )

    def _on_render_failed(self, message: str) -> None:
        """Present a structured include/input trace instead of a flat error string."""
        builder = getattr(self, "_latex_diagnostic_builder", None)
        source_path = self._editor_panel.current_path()
        if builder is None or source_path is None:
            super()._on_render_failed(message)
            return

        diagnostic = builder.build(
            message=message,
            source_path=source_path,
            source=self._editor_panel.current_content(),
        )
        self._preview_panel.show_latex_error(diagnostic)

    def _open_latex_diagnostic_location(
        self,
        path: str,
        line: int,
        column: int,
    ) -> None:
        """Open a diagnostic source file and jump to its exact source location."""
        source_path = Path(path).expanduser().resolve(strict=False)
        if not source_path.is_file():
            self.statusBar().showMessage(
                f"Diagnostic source no longer exists: {source_path}",
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

    def _sync_graphic_update_event(self) -> None:
        """Force Source and Visual image caches to follow every accepted iPad save event."""
        previous_signature = getattr(self, "_graphic_update_event_signature", None)
        super()._sync_graphic_update_event()
        if getattr(self, "_graphic_update_event_signature", None) == previous_signature:
            return

        source_controller = getattr(
            self,
            "_source_graphic_preview_controller",
            None,
        )
        if source_controller is not None:
            source_controller.schedule_layout_refresh()

        refresh_visual = getattr(
            self._editor_panel,
            "refresh_current_visual_graphics",
            None,
        )
        if callable(refresh_visual):
            refresh_visual()

    def _reload_yaml_settings(self) -> bool:
        """Keep Preview path semantics synchronized with search.default_path."""
        loaded = super()._reload_yaml_settings()
        if not loaded:
            return False
        self._configure_workspace_input_resolver()
        diagnostic_builder = getattr(
            self,
            "_latex_diagnostic_builder",
            None,
        )
        if diagnostic_builder is not None:
            diagnostic_builder.configure(
                default_path=self._app_settings.search_default_path,
                template_path=self._app_settings.preview_latex_template_path,
                beamer_template_path=(
                    self._app_settings.preview_latex_beamer_template_path
                ),
            )
        graphic_path_controller = getattr(
            self,
            "_graphic_open_session_path_controller",
            None,
        )
        if graphic_path_controller is not None:
            graphic_path_controller.reload_settings()
        self._refresh_current_preview(immediate=True)
        return True

    def _sync_external_file_changes(self) -> None:
        """Defer external-file reconciliation while workspace workers mutate related files."""
        filesystem = getattr(
            self,
            "_workspace_filesystem_operation_controller",
            None,
        )
        if filesystem is not None and filesystem.has_pending_work:
            return
        references = getattr(
            self,
            "_workspace_reference_maintenance_controller",
            None,
        )
        if references is not None and references.has_pending_work:
            return
        super()._sync_external_file_changes()

    def _restore_session(self) -> None:
        """Configure workspace paths before restored tabs can request Preview."""
        self._configure_workspace_input_resolver()
        self._sanitize_session_string_lists()
        super()._restore_session()

    def _save_session(self) -> None:
        """Prevent empty Python lists from persisting as Qt @Invalid values."""
        super()._save_session()
        self._sanitize_session_string_lists()
        self._session_settings.sync()

    def _sanitize_session_string_lists(self) -> None:
        """Normalize persisted string-list values used by editor and Navigator state."""
        settings = getattr(self, "_session_settings", None)
        if settings is None:
            return
        SessionStringListSanitizer(settings).normalize_many(
            self._SESSION_STRING_LIST_KEYS
        )
