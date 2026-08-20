from pathlib import Path
import json
import re
import mimetypes
import shutil

from PySide6.QtCore import (
    QRect,
    QSettings,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QSplitter,
)

from nd_mind_mirror.core.completion.latex.latex_completion_provider import (
    LatexCompletionProvider,
)
from nd_mind_mirror.core.document.latex.latex_document import LatexDocument
from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.core.workspace.path.path_reference_updater import (
    PathReferenceUpdater,
)
from nd_mind_mirror.ui.input.double_shift.double_shift_event_filter import (
    DoubleShiftEventFilter,
)
from nd_mind_mirror.ui.input.ctrl_tab.ctrl_tab_event_filter import (
    CtrlTabEventFilter,
)
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.panel.file_system.file_system_panel import (
    FileSystemPanel,
)
from nd_mind_mirror.ui.panel.preview.preview_panel import PreviewPanel
from nd_mind_mirror.ui.panel.structure.latex_structure_panel import (
    LatexStructurePanel,
)
from nd_mind_mirror.ui.search.window.search_window import SearchWindow
from nd_mind_mirror.ui.switcher.recent_file.recent_file_switcher import (
    RecentFileSwitcher,
)
from nd_mind_mirror.ui.window.base.window import Window


class MainWindow(Window):
    _EXTERNAL_OPEN_SUFFIXES = {
        ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".bmp", ".svg", ".tif", ".tiff",
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "nd_mind_mirror_project"
        )
        self.resize(1500, 900)

        self._restoring_session = True
        self._app_settings = YamlSettings()
        self._session_settings = QSettings(
            str(self._app_settings.session_settings_path),
            QSettings.Format.IniFormat,
        )
        self._migrate_legacy_qsettings_if_needed()
        self._file_signatures: dict[Path, tuple[int, int]] = {}
        self._preview_dependency_signatures: dict[Path, tuple[int, int] | None] = {}
        self._recent_file_paths: list[Path] = []
        self._deferred_window_rect: tuple[int, int, int, int] | None = None
        self._deferred_window_maximized = False
        self._deferred_main_splitter_sizes: list[int] | None = None
        self._deferred_navigator_splitter_sizes: list[int] | None = None
        self._ui_layout_applied = False
        legacy_ui_state = (
            Path.home() / ".config" / "nd_mind_mirror_project" / "ui_state.json"
        )
        self._app_settings.migrate_legacy_ui_state(legacy_ui_state)
        self._ui_state_path = self._app_settings.ui_state_path

        QApplication.setCursorFlashTime(
            self._app_settings.editor_cursor_flash_time_ms
        )

        self._document = LatexDocument()
        self._renderer = LatexRenderer(
            template_path=(
                self._app_settings.preview_latex_template_path
            ),
            beamer_template_path=(
                self._app_settings.preview_latex_beamer_template_path
            ),
            shell_escape=(
                self._app_settings.preview_shell_escape
            ),
            debounce_ms=(
                self._app_settings.preview_debounce_ms
            ),
            cursor_sync_enabled=(
                self._app_settings.preview_cursor_sync_enabled
            ),
            cursor_sync_debounce_ms=(
                self._app_settings.preview_cursor_sync_debounce_ms
            ),
            large_document_threshold_chars=(
                self._app_settings.preview_large_document_threshold_chars
            ),
            large_document_debounce_ms=(
                self._app_settings.preview_large_document_debounce_ms
            ),
            parent=self,
        )

        completions = LatexCompletionProvider().load()

        self._file_system_panel = FileSystemPanel(
            self
        )
        self._file_system_panel.apply_settings(
            indent_width=self._app_settings.navigator_indent_width,
            root_path=self._app_settings.search_default_path,
            ignore_file_path=(
                self._app_settings.search_ignore_file_path
            ),
            row_height=self._app_settings.navigator_row_height,
            latex_templates=self._app_settings.new_latex_file_templates,
        )

        self._structure_panel = LatexStructurePanel(
            self
        )
        self._structure_panel.apply_settings(
            indent_width=self._app_settings.navigator_indent_width,
            row_height=self._app_settings.navigator_row_height,
            tab_size=self._app_settings.editor_tab_size,
        )

        self._editor_panel = EditorPanel(
            completions=completions,
            app_settings=self._app_settings,
            parent=self,
        )
        self._preview_panel = PreviewPanel(
            self
        )
        self._preview_panel.apply_settings(
            default_zoom_percent=(
                self._app_settings.preview_default_zoom_percent
            ),
            auto_fit_on_open=(
                self._app_settings.preview_auto_fit_on_open
            ),
            fit_width_percent=(
                self._app_settings.preview_fit_width_percent
            ),
        )

        self._search_window = SearchWindow(
            root_path=self._app_settings.search_default_path,
            max_results=self._app_settings.search_max_results,
            debounce_ms=self._app_settings.search_debounce_ms,
            ignore_file_path=(
                self._app_settings.search_ignore_file_path
            ),
            fuzzy_threshold=(
                self._app_settings.search_fuzzy_threshold
            ),
            window_width=(
                self._app_settings.search_window_width
            ),
            window_height=(
                self._app_settings.search_window_height
            ),
            tree_indent_width=(
                self._app_settings.search_tree_indent_width
            ),
            hierarchical_path_matching=(
                self._app_settings.search_hierarchical_path_matching
            ),
            parent=self,
        )

        self._double_shift_filter = DoubleShiftEventFilter(
            interval_ms=(
                self._app_settings.double_shift_interval_ms
            ),
            parent=self,
        )
        self._ctrl_tab_filter = CtrlTabEventFilter(
            parent=self
        )
        self._recent_file_switcher = RecentFileSwitcher(
            self
        )

        application = QApplication.instance()

        if application is not None:
            application.installEventFilter(
                self._double_shift_filter
            )
            application.installEventFilter(
                self._ctrl_tab_filter
            )

        self._navigator_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self,
        )
        self._navigator_splitter.setChildrenCollapsible(False)
        self._navigator_splitter.setOpaqueResize(True)
        self._navigator_splitter.setHandleWidth(
            self._app_settings.splitter_handle_width
        )
        self._navigator_splitter.addWidget(
            self._file_system_panel
        )
        self._navigator_splitter.addWidget(
            self._structure_panel
        )
        self._navigator_splitter.setStretchFactor(0, 3)
        self._navigator_splitter.setStretchFactor(1, 2)

        self._splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self,
        )
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setOpaqueResize(True)
        self._splitter.setHandleWidth(
            self._app_settings.splitter_handle_width
        )
        self._splitter.addWidget(
            self._navigator_splitter
        )
        self._splitter.addWidget(
            self._editor_panel
        )
        self._splitter.addWidget(
            self._preview_panel
        )
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setStretchFactor(2, 2)

        self.setCentralWidget(
            self._splitter
        )

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(
            self._autosave_modified_documents
        )

        self._external_file_sync_timer = QTimer(self)
        self._external_file_sync_timer.timeout.connect(
            self._sync_external_file_changes
        )

        self._layout_save_timer = QTimer(self)
        self._layout_save_timer.setSingleShot(True)
        self._layout_save_timer.setInterval(180)
        self._layout_save_timer.timeout.connect(
            self._save_ui_layout_state
        )

        self._preview_edit_highlight_timer = QTimer(self)
        self._preview_edit_highlight_timer.setSingleShot(True)
        self._preview_edit_highlight_timer.setInterval(
            self._app_settings.preview_edit_location_highlight_debounce_ms
        )
        self._preview_edit_highlight_timer.timeout.connect(
            self._apply_pending_preview_edit_highlight
        )
        self._pending_preview_edit_highlight = ""
        self._last_preview_edit_highlight = ""

        self._create_actions()
        self._connect_signals()
        self._configure_autosave()
        self._configure_external_file_sync()
        self._restore_session()

        self._restoring_session = False
        # Geometry and splitter widths are restored only after the window has
        # entered the event loop. Restoring stale QSplitter/QWidget binary
        # state during construction caused black-window startup failures on
        # some Qt/Wayland/X11 combinations.
        self.statusBar().showMessage(
            "Ready"
        )

    def _create_actions(self) -> None:
        self._open_action = QAction(
            "Open...",
            self,
        )
        self._open_action.setShortcut(
            QKeySequence.StandardKey.Open
        )
        self._open_action.triggered.connect(
            self._open_dialog
        )

        self._close_tab_action = QAction(
            "Close Tab",
            self,
        )
        self._close_tab_action.setShortcut(
            QKeySequence("Ctrl+W")
        )
        self._close_tab_action.triggered.connect(
            self._editor_panel.request_close_current_tab
        )

        self._save_action = QAction(
            "Save",
            self,
        )
        self._save_action.setShortcut(
            QKeySequence.StandardKey.Save
        )
        self._save_action.triggered.connect(
            self._save_current_document
        )

        self._format_action = QAction(
            "Format LaTeX",
            self,
        )
        self._format_action.setShortcut(
            QKeySequence(
                "Ctrl+Shift+F"
            )
        )
        self._format_action.triggered.connect(
            self._format_current_document
        )

        self._export_action = QAction(
            "Export PDF...",
            self,
        )
        self._export_action.triggered.connect(
            self._export_pdf
        )

        self._find_in_tab_action = QAction(
            "Find in Current Tab",
            self,
        )
        self._find_in_tab_action.setShortcut(QKeySequence("Ctrl+F"))
        self._find_in_tab_action.triggered.connect(
            lambda: self._editor_panel.show_find_replace(False)
        )

        self._replace_in_tab_action = QAction(
            "Replace in Current Tab",
            self,
        )
        self._replace_in_tab_action.setShortcut(QKeySequence("Ctrl+R"))
        self._replace_in_tab_action.triggered.connect(
            lambda: self._editor_panel.show_find_replace(True)
        )

        self._search_action = QAction(
            "Search Files (Double Shift)",
            self,
        )
        self._search_action.triggered.connect(
            self._show_search_window
        )

        self._reload_settings_action = QAction(
            "Reload settings.yaml",
            self,
        )
        self._reload_settings_action.triggered.connect(
            self._reload_yaml_settings
        )

        self._edit_settings_action = QAction(
            "Edit settings.yaml",
            self,
        )
        self._edit_settings_action.triggered.connect(
            self._edit_settings_file
        )

        self._edit_latex_shortcuts_action = QAction(
            "Edit latex_shortcuts.yaml",
            self,
        )
        self._edit_latex_shortcuts_action.triggered.connect(
            self._edit_latex_shortcuts_file
        )

        self._edit_preview_template_action = QAction(
            "Edit LaTeX preview template",
            self,
        )
        self._edit_preview_template_action.triggered.connect(
            self._edit_preview_template
        )

        self._edit_beamer_preview_template_action = QAction(
            "Edit Beamer preview template",
            self,
        )
        self._edit_beamer_preview_template_action.triggered.connect(
            self._edit_beamer_preview_template
        )

        self._toggle_bookmark_action = QAction(
            "Toggle Bookmark at Cursor", self
        )
        self._toggle_bookmark_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self._toggle_bookmark_action.triggered.connect(
            self._editor_panel.toggle_current_bookmark
        )

        file_menu = self.menuBar().addMenu(
            "File"
        )
        file_menu.addAction(
            self._open_action
        )
        file_menu.addAction(
            self._save_action
        )
        file_menu.addAction(
            self._close_tab_action
        )
        file_menu.addSeparator()
        file_menu.addAction(
            self._export_action
        )

        edit_menu = self.menuBar().addMenu(
            "Edit"
        )
        edit_menu.addAction(
            self._format_action
        )

        search_menu = self.menuBar().addMenu(
            "Search"
        )
        search_menu.addAction(
            self._find_in_tab_action
        )
        search_menu.addAction(
            self._replace_in_tab_action
        )
        search_menu.addSeparator()
        search_menu.addAction(
            self._search_action
        )

        self._bookmarks_menu = self.menuBar().addMenu("Bookmarks")
        self._bookmarks_menu.aboutToShow.connect(self._refresh_bookmarks_menu)
        self._refresh_bookmarks_menu()

        settings_menu = self.menuBar().addMenu(
            "Settings"
        )
        settings_menu.addAction(
            self._edit_settings_action
        )
        settings_menu.addAction(
            self._edit_latex_shortcuts_action
        )
        settings_menu.addAction(
            self._edit_preview_template_action
        )
        settings_menu.addAction(
            self._edit_beamer_preview_template_action
        )
        settings_menu.addAction(
            self._reload_settings_action
        )

        self._save_action.setEnabled(False)

    def _connect_signals(self) -> None:
        self._file_system_panel.latex_file_selected.connect(
            self._open_path_from_navigator
        )
        self._file_system_panel.state_changed.connect(
            self._save_session
        )
        self._file_system_panel.path_about_to_move.connect(
            lambda _path: self._autosave_modified_documents()
        )
        self._file_system_panel.path_renamed.connect(
            self._on_navigator_path_renamed
        )
        self._file_system_panel.path_deleted.connect(
            self._on_navigator_path_deleted
        )
        self._file_system_panel.path_created.connect(
            self._on_navigator_path_created
        )
        self._structure_panel.line_activated.connect(
            self._editor_panel.go_to_line
        )

        self._editor_panel.current_document_changed.connect(
            self._on_current_document_changed
        )
        self._editor_panel.current_content_changed.connect(
            self._on_current_content_changed
        )
        self._editor_panel.current_modification_changed.connect(
            self._on_current_modification_changed
        )
        self._editor_panel.current_cursor_changed.connect(
            self._on_current_cursor_changed
        )
        self._editor_panel.current_view_changed.connect(
            self._on_current_view_changed
        )
        self._editor_panel.bookmarks_changed.connect(
            self._on_bookmarks_changed
        )
        self._editor_panel.capacity_reached.connect(
            self._show_warning
        )
        self._editor_panel.tab_close_requested.connect(
            self._handle_tab_close_request
        )
        self._editor_panel.settings_apply_requested.connect(
            self._apply_settings_from_editor
        )
        self._editor_panel.active_tab_clicked.connect(
            self._reveal_active_editor_tab
        )

        self._preview_panel.export_requested.connect(
            self._export_pdf
        )

        self._renderer.rendered.connect(
            self._preview_panel.show_pdf
        )
        self._renderer.failed.connect(
            self._on_render_failed
        )
        self._renderer.source_position_mapped.connect(
            self._preview_panel.preview.scroll_to_source_location
        )
        self._renderer.dependencies_changed.connect(
            self._on_renderer_dependencies_changed
        )

        self._double_shift_filter.activated.connect(
            self._show_search_window
        )
        self._search_window.latex_file_selected.connect(
            self._open_path
        )

        self._ctrl_tab_filter.cycle_requested.connect(
            self._cycle_recent_file_switcher
        )
        self._ctrl_tab_filter.commit_requested.connect(
            self._commit_recent_file_switcher
        )
        self._ctrl_tab_filter.cancel_requested.connect(
            self._cancel_recent_file_switcher
        )

        self._splitter.splitterMoved.connect(
            lambda position, index:
            self._schedule_ui_layout_save()
        )
        self._navigator_splitter.splitterMoved.connect(
            lambda position, index:
            self._schedule_ui_layout_save()
        )

    def _open_dialog(self) -> None:
        current = self._editor_panel.current_path()

        start_directory = (
            str(current.parent)
            if current is not None
            else str(Path.home())
        )

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open LaTeX file",
            start_directory,
            "Text files (*);;LaTeX files (*.tex);;Markdown files (*.md *.markdown);;YAML files (*.yaml *.yml);;All files (*)",
        )

        if path:
            self._open_path(path)


    def _reveal_active_editor_tab(self, path: str) -> None:
        """Center and highlight the backing file for a clicked editor tab."""
        self._file_system_panel.select_path(
            path,
            force_reveal=True,
        )

    def _open_path_from_navigator(self, path: str) -> None:
        self._open_path(
            path,
            reveal_in_navigator=False,
        )

    def _open_path(
        self,
        path: str,
        select: bool = True,
        reveal_in_navigator: bool = True,
    ) -> None:
        file_path = Path(
            path
        ).expanduser().resolve()

        if file_path.suffix.lower() in self._EXTERNAL_OPEN_SUFFIXES:
            self._open_with_desktop_application(file_path)
            if reveal_in_navigator:
                self._file_system_panel.select_path(file_path)
            return

        if file_path.is_file() and not self._is_text_file(file_path):
            self._open_with_desktop_application(file_path)
            if reveal_in_navigator:
                self._file_system_panel.select_path(file_path)
            return

        if self._editor_panel.activate_path(
            file_path
        ):
            if reveal_in_navigator:
                self._file_system_panel.select_path(
                    file_path
                )
            self._refresh_current_preview(immediate=True)
            self._save_session()
            return

        try:
            content = self._load_editor_file(file_path)
        except (
            OSError,
            ValueError,
        ) as exc:
            QMessageBox.critical(
                self,
                "Open error",
                str(exc),
            )
            return

        self._remember_file_signature(file_path)

        opened = self._editor_panel.open_file(
            file_path,
            content,
            select=select,
        )

        if opened and select and reveal_in_navigator:
            self._file_system_panel.select_path(
                file_path
            )

        if opened and select:
            self._refresh_current_preview(immediate=True)

        if opened:
            self._save_session()

    def _open_with_desktop_application(self, file_path: Path) -> None:
        if not file_path.is_file():
            self._show_warning(f"File does not exist: {file_path}")
            return
        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(file_path))
        )
        if not opened:
            self._show_warning(
                "Ubuntu could not open this file with its default application: "
                f"{file_path}"
            )

    def _load_editor_file(self, file_path: Path) -> str:
        if file_path.suffix.lower() in {".tex", ".tikz"}:
            return self._document.load(file_path)

        if not self._is_text_file(file_path):
            raise ValueError(f"{file_path.name} is not a text file.")

        for encoding in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeError:
                continue
        raise ValueError(f"Could not decode text file: {file_path}")

    def _is_text_file(self, file_path: Path) -> bool:
        """Return True for editable text while rejecting obvious binary data."""
        if not file_path.is_file():
            return False

        suffix = file_path.suffix.lower()
        if suffix in {
            ".tex", ".tikz", ".yaml", ".yml", ".md", ".markdown", ".txt", ".rst",
            ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".c",
            ".h", ".hpp", ".cc", ".cpp", ".cs", ".go", ".rs", ".rb",
            ".php", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".sql",
            ".html", ".htm", ".css", ".scss", ".sass", ".less", ".xml",
            ".json", ".toml", ".ini", ".cfg", ".conf", ".env", ".csv",
            ".tsv", ".log", ".bib", ".sty", ".cls", ".lua", ".r", ".jl",
            ".kt", ".kts", ".swift", ".scala", ".clj", ".edn", ".vue",
            ".svelte", ".dockerfile", ".make", ".mk",
        }:
            return True

        if file_path.name.casefold() in {
            "readme", "readme.md", "license", "copying", "makefile",
            "dockerfile", ".gitignore", ".gitattributes", ".editorconfig",
        }:
            return True

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith("text/"):
            return True

        try:
            sample = file_path.read_bytes()[:8192]
        except OSError:
            return False
        if not sample:
            return True
        if b"\x00" in sample:
            return False
        try:
            sample.decode("utf-8")
            return True
        except UnicodeDecodeError:
            pass
        # Latin-1 itself is always decodable, so reject samples with too many
        # control bytes before using it as a fallback for legacy text files.
        controls = sum(
            1 for value in sample
            if value < 32 and value not in {9, 10, 12, 13}
        )
        return controls / max(len(sample), 1) < 0.02

    def _save_current_document(self) -> None:
        path = self._editor_panel.current_path()

        if (
            path is None
            or not self._editor_panel.is_current_modified()
        ):
            return

        content = (
            self._editor_panel.current_content()
        )

        if not self._save_document(
            path,
            content,
            show_error=True,
        ):
            return

        self._editor_panel.mark_saved(
            path
        )
        self._save_action.setEnabled(
            False
        )

        self.statusBar().showMessage(
            f"Saved {path}",
            3500,
        )

    def _save_document(
        self,
        path: Path,
        content: str,
        show_error: bool,
    ) -> bool:
        try:
            self._document.save(
                path,
                content,
            )
        except OSError as exc:
            if show_error:
                QMessageBox.critical(
                    self,
                    "Save error",
                    str(exc),
                )
            else:
                self.statusBar().showMessage(
                    f"Autosave failed: {path} — {exc}",
                    5000,
                )
            return False

        self._remember_file_signature(path)

        if path.resolve() == self._app_settings.latex_shortcuts_file_path.resolve():
            self._editor_panel.apply_settings(
                self._app_settings
            )
            self.statusBar().showMessage(
                f"Reloaded LaTeX shortcuts from {path}",
                3500,
            )

        return True

    def _autosave_modified_documents(
        self,
    ) -> None:
        if not self._app_settings.autosave_enabled:
            return

        # Detect editor-external writes before autosave gets a chance to
        # overwrite them.
        if self._app_settings.external_file_sync_enabled:
            self._sync_external_file_changes()

        for (
            path,
            content,
        ) in self._editor_panel.modified_documents():
            if self._save_document(
                path,
                content,
                show_error=False,
            ):
                self._editor_panel.mark_saved(
                    path
                )

        self._save_action.setEnabled(
            self._editor_panel.is_current_modified()
        )

    def _configure_autosave(
        self,
    ) -> None:
        self._autosave_timer.stop()

        if not self._app_settings.autosave_enabled:
            return

        self._autosave_timer.setInterval(
            self._app_settings.autosave_interval_ms
        )
        self._autosave_timer.start()

    def _configure_external_file_sync(
        self,
    ) -> None:
        self._external_file_sync_timer.stop()

        if not self._app_settings.external_file_sync_enabled:
            return

        self._external_file_sync_timer.setInterval(
            self._app_settings.external_file_sync_interval_ms
        )
        self._external_file_sync_timer.start()

    def _sync_external_file_changes(
        self,
    ) -> None:
        for path in self._editor_panel.open_paths():
            signature = self._file_signature(path)
            if signature is None:
                continue

            known = self._file_signatures.get(path)
            if known is None:
                self._file_signatures[path] = signature
                continue

            if signature == known:
                continue

            try:
                content = self._load_editor_file(path)
            except (OSError, ValueError):
                self._file_signatures[path] = signature
                continue

            editor_content = (
                self._editor_panel.content_for_path(path)
            )

            if editor_content != content:
                self._editor_panel.replace_content_from_disk(
                    path,
                    content,
                )

                if path.resolve() == self._app_settings.latex_shortcuts_file_path.resolve():
                    self._editor_panel.apply_settings(
                        self._app_settings
                    )

                self.statusBar().showMessage(
                    f"Reloaded external change: {path}",
                    3500,
                )

            self._file_signatures[path] = signature

        self._sync_preview_dependency_changes()

    def _on_renderer_dependencies_changed(self, paths: object) -> None:
        """Track files used by the currently rendered LaTeX document.

        Included TikZ/TeX files do not need to be open in an editor tab. When
        an iPad/Dropbox/WebSocket bridge rewrites one of them, the dependency
        timer sees the signature change and asks the active parent document to
        render again without modifying its source.
        """
        signatures: dict[Path, tuple[int, int] | None] = {}
        if isinstance(paths, (list, tuple, set)):
            for raw_path in paths:
                try:
                    path = Path(str(raw_path)).expanduser().resolve()
                except (OSError, ValueError):
                    continue
                signatures[path] = self._file_signature(path)
        self._preview_dependency_signatures = signatures

    def _sync_preview_dependency_changes(self) -> None:
        if not self._preview_dependency_signatures:
            return

        current = self._editor_panel.current_path()
        if current is None or current.suffix.lower() not in {".tex", ".tikz"}:
            return

        changed: list[Path] = []
        for path, known_signature in list(
            self._preview_dependency_signatures.items()
        ):
            signature = self._file_signature(path)
            if signature == known_signature:
                continue
            self._preview_dependency_signatures[path] = signature
            changed.append(path)

        if not changed:
            return

        self.statusBar().showMessage(
            "LaTeX dependency changed: "
            + ", ".join(path.name for path in changed[:3]),
            2500,
        )
        if any(path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".svg"} for path in changed):
            self._editor_panel.refresh_current_visual_graphics()
        self._refresh_current_preview(immediate=False)

    def _file_signature(
        self,
        path: Path,
    ) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None

        return (
            int(stat.st_mtime_ns),
            int(stat.st_size),
        )

    def _remember_file_signature(
        self,
        path: str | Path,
    ) -> None:
        file_path = Path(
            path
        ).expanduser().resolve()
        signature = self._file_signature(file_path)
        if signature is not None:
            self._file_signatures[file_path] = signature

    def _format_current_document(
        self,
    ) -> None:
        self._editor_panel.format_current_document()

    def _handle_tab_close_request(
        self,
        index: int,
        path_text: str,
        modified: bool,
    ) -> None:
        path = Path(path_text)

        if modified:
            decision = QMessageBox.question(
                self,
                "Unsaved changes",
                f"{path.name} has unsaved changes.",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if (
                decision
                == QMessageBox.StandardButton.Cancel
            ):
                return

            if (
                decision
                == QMessageBox.StandardButton.Save
            ):
                content = (
                    self._editor_panel.content_at(
                        index
                    )
                )

                if not self._save_document(
                    path,
                    content,
                    show_error=True,
                ):
                    return

        self._editor_panel.close_tab(
            index
        )
        self._save_session()

    def _export_pdf(self) -> None:
        source_pdf = (
            self._preview_panel
            .preview
            .current_pdf_path
        )

        if (
            source_pdf is None
            or not source_pdf.is_file()
        ):
            QMessageBox.information(
                self,
                "Export PDF",
                "There is no successfully rendered PDF "
                "to export yet.",
            )
            return

        current_tex = (
            self._editor_panel.current_path()
        )

        default_path = (
            current_tex.with_suffix(".pdf")
            if current_tex is not None
            else Path.home() / "preview.pdf"
        )

        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            str(default_path),
            "PDF files (*.pdf)",
        )

        if not destination:
            return

        destination_path = Path(
            destination
        ).expanduser()

        if (
            destination_path.suffix.lower()
            != ".pdf"
        ):
            destination_path = (
                destination_path.with_suffix(
                    ".pdf"
                )
            )

        try:
            shutil.copy2(
                source_pdf,
                destination_path,
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Export PDF",
                str(exc),
            )
            return

        self.statusBar().showMessage(
            f"Exported PDF to {destination_path}",
            5000,
        )

    def _show_search_window(self) -> None:
        self._search_window.show_and_focus()

    def _edit_settings_file(self) -> None:
        settings_path = self._app_settings.settings_path

        if not settings_path.is_file():
            QMessageBox.warning(
                self,
                "Settings",
                f"Settings file does not exist:\n{settings_path}",
            )
            return

        self._open_path(str(settings_path))

    def _edit_latex_shortcuts_file(self) -> None:
        shortcuts_path = (
            self._app_settings.latex_shortcuts_file_path
        )

        if not shortcuts_path.is_file():
            QMessageBox.warning(
                self,
                "LaTeX shortcuts",
                f"Shortcut file does not exist:\n{shortcuts_path}",
            )
            return

        self._open_path(str(shortcuts_path))

    def _edit_preview_template(self) -> None:
        template_path = (
            self._app_settings.preview_latex_template_path
        )

        if not template_path.is_file():
            QMessageBox.warning(
                self,
                "Preview template",
                f"Template file does not exist:\n{template_path}",
            )
            return

        self._open_path(
            str(template_path)
        )

    def _edit_beamer_preview_template(self) -> None:
        template_path = (
            self._app_settings.preview_latex_beamer_template_path
        )

        if not template_path.is_file():
            QMessageBox.warning(
                self,
                "Beamer preview template",
                f"Template file does not exist:\n{template_path}",
            )
            return

        self._open_path(
            str(template_path)
        )

    def _cycle_recent_file_switcher(
        self,
        direction: int,
    ) -> None:
        paths = [
            path
            for path in self._recent_file_paths
            if path in self._editor_panel.open_paths()
        ]

        for path in self._editor_panel.open_paths():
            if path not in paths:
                paths.append(path)

        if not self._recent_file_switcher.isVisible():
            self._recent_file_switcher.begin(
                paths,
                direction,
            )
            return

        self._recent_file_switcher.step(direction)

    def _commit_recent_file_switcher(self) -> None:
        path = self._recent_file_switcher.selected_path()
        self._recent_file_switcher.dismiss()

        if path is None:
            return

        self._open_path(str(path))

    def _cancel_recent_file_switcher(self) -> None:
        self._recent_file_switcher.dismiss()

    def _touch_recent_file(
        self,
        path: str | Path,
    ) -> None:
        file_path = Path(
            path
        ).expanduser().resolve()
        self._recent_file_paths = [
            item
            for item in self._recent_file_paths
            if item != file_path
        ]
        self._recent_file_paths.insert(0, file_path)
        self._recent_file_paths = (
            self._recent_file_paths[
                : self._app_settings.editor_max_open_tabs
            ]
        )

    def _apply_settings_from_editor(self) -> None:
        settings_path = self._app_settings.settings_path.resolve()
        current_path = self._editor_panel.current_path()
        if current_path is None or current_path.resolve() != settings_path:
            return

        content = self._editor_panel.current_content()
        if not self._save_document(
            settings_path,
            content,
            show_error=True,
        ):
            return

        self._editor_panel.mark_saved(settings_path)
        self._save_action.setEnabled(False)
        self._reload_yaml_settings()

    def _reload_yaml_settings(self) -> bool:
        if not self._app_settings.reload():
            message = (
                self._app_settings.last_reload_error
                or "Could not reload settings.yaml."
            )
            self.statusBar().showMessage(
                f"Settings not applied: {message}",
                7000,
            )
            return False

        QApplication.setCursorFlashTime(
            self._app_settings.editor_cursor_flash_time_ms
        )

        self._editor_panel.apply_settings(
            self._app_settings
        )
        self._file_system_panel.apply_settings(
            indent_width=self._app_settings.navigator_indent_width,
            root_path=self._app_settings.search_default_path,
            ignore_file_path=(
                self._app_settings.search_ignore_file_path
            ),
            row_height=self._app_settings.navigator_row_height,
            latex_templates=self._app_settings.new_latex_file_templates,
        )
        self._structure_panel.apply_settings(
            indent_width=self._app_settings.navigator_indent_width,
            row_height=self._app_settings.navigator_row_height,
            tab_size=self._app_settings.editor_tab_size,
        )
        self._search_window.apply_settings(
            root_path=self._app_settings.search_default_path,
            max_results=self._app_settings.search_max_results,
            debounce_ms=self._app_settings.search_debounce_ms,
            ignore_file_path=(
                self._app_settings.search_ignore_file_path
            ),
            fuzzy_threshold=(
                self._app_settings.search_fuzzy_threshold
            ),
            window_width=(
                self._app_settings.search_window_width
            ),
            window_height=(
                self._app_settings.search_window_height
            ),
            tree_indent_width=(
                self._app_settings.search_tree_indent_width
            ),
            hierarchical_path_matching=(
                self._app_settings.search_hierarchical_path_matching
            ),
        )
        self._preview_panel.apply_settings(
            default_zoom_percent=(
                self._app_settings.preview_default_zoom_percent
            ),
            auto_fit_on_open=(
                self._app_settings.preview_auto_fit_on_open
            ),
            fit_width_percent=(
                self._app_settings.preview_fit_width_percent
            ),
        )
        self._renderer.apply_settings(
            template_path=(
                self._app_settings.preview_latex_template_path
            ),
            shell_escape=(
                self._app_settings.preview_shell_escape
            ),
            debounce_ms=(
                self._app_settings.preview_debounce_ms
            ),
            beamer_template_path=(
                self._app_settings.preview_latex_beamer_template_path
            ),
            cursor_sync_enabled=(
                self._app_settings.preview_cursor_sync_enabled
            ),
            cursor_sync_debounce_ms=(
                self._app_settings.preview_cursor_sync_debounce_ms
            ),
            large_document_threshold_chars=(
                self._app_settings.preview_large_document_threshold_chars
            ),
            large_document_debounce_ms=(
                self._app_settings.preview_large_document_debounce_ms
            ),
        )
        self._double_shift_filter.set_interval_ms(
            self._app_settings.double_shift_interval_ms
        )
        self._splitter.setHandleWidth(
            self._app_settings.splitter_handle_width
        )
        self._navigator_splitter.setHandleWidth(
            self._app_settings.splitter_handle_width
        )
        self._configure_autosave()
        self._configure_external_file_sync()
        self._preview_edit_highlight_timer.setInterval(
            self._app_settings.preview_edit_location_highlight_debounce_ms
        )
        if not self._app_settings.preview_edit_location_highlight_enabled:
            self._pending_preview_edit_highlight = ""
            self._preview_panel.preview.set_edit_highlight("")

        self.statusBar().showMessage(
            f"Applied {self._app_settings.settings_path}",
            5000,
        )
        return True

    def _on_current_document_changed(
        self,
        path: str,
        content: str,
    ) -> None:
        self._touch_recent_file(path)
        self._structure_panel.set_document(
            path,
            content,
            immediate=True,
        )
        self._render_path_content(
            path,
            content,
            immediate=True,
        )

        self._file_system_panel.select_path(
            path
        )

        self._save_action.setEnabled(
            self._editor_panel.is_current_modified()
        )
        self._format_action.setEnabled(
            Path(path).suffix.lower() in {".tex", ".tikz"}
        )

        self._save_session()

    def _on_current_content_changed(
        self,
        path: str,
        content: str,
    ) -> None:
        current = (
            self._editor_panel.current_path()
        )

        if current is None:
            return

        if (
            Path(path).resolve()
            != current
        ):
            return

        self._structure_panel.set_document(
            path,
            content,
            immediate=False,
        )
        self._render_path_content(
            path,
            content,
            immediate=False,
        )

    def _refresh_current_preview(
        self,
        immediate: bool,
    ) -> None:
        path = self._editor_panel.current_path()
        if path is None:
            return

        self._render_path_content(
            str(path),
            self._editor_panel.current_content(),
            immediate=immediate,
        )

    def _render_path_content(
        self,
        path: str | Path,
        content: str,
        immediate: bool,
    ) -> None:
        file_path = Path(path).expanduser().resolve()

        suffix = file_path.suffix.lower()
        if suffix in {".tex", ".tikz"}:
            self._preview_panel.show_latex_mode()
            self._preview_panel.preview.set_source_document(file_path)
        elif suffix in {".md", ".markdown"} or file_path.name.casefold() == "readme.md":
            self._preview_panel.show_markdown(content, file_path)
            return
        else:
            if file_path.resolve() == self._app_settings.settings_path.resolve():
                self._preview_panel.show_message(
                    "settings.yaml is open in the editor. Changes may be saved "
                    "normally, but they are not applied until you press Apply "
                    "above the editor."
                )
            else:
                self._preview_panel.show_message(
                    f"No rendered preview for {file_path.name}."
                )
            return

        self._renderer.render(
            content,
            source_path=file_path,
            immediate=immediate,
        )

    def _on_render_failed(self, message: str) -> None:
        # Keep the last successful PDF visible for transient syntax states
        # while the user is typing.  The preview object only replaces the PDF
        # with the error page when the current source has never rendered
        # successfully.
        self._preview_panel.preview.show_error(message)
        first_line = next(
            (line.strip() for line in str(message).splitlines() if line.strip()),
            "LaTeX preview failed.",
        )
        self.statusBar().showMessage(first_line, 7000)

    def _on_current_cursor_changed(
        self,
        path: str,
        line: int,
        column: int,
    ) -> None:
        if not self._request_preview_source_position(path, line, column):
            return
        if self._app_settings.preview_edit_location_highlight_enabled:
            editor = self._editor_panel.current_editor()
            if isinstance(editor, LatexEditor):
                self._pending_preview_edit_highlight = (
                    editor.active_preview_highlight_text()
                )
            else:
                self._pending_preview_edit_highlight = self._edit_phrase_for_position(
                    path, line, column
                )
            self._preview_edit_highlight_timer.start()

    def _on_current_view_changed(
        self,
        path: str,
        line: int,
        column: int,
    ) -> None:
        self._request_preview_source_position(path, line, column)

    def _request_preview_source_position(
        self, path: str, line: int, column: int
    ) -> bool:
        current = self._editor_panel.current_path()
        if current is None:
            return False
        source_path = Path(path).expanduser().resolve()
        if source_path != current or source_path.suffix.lower() not in {".tex", ".tikz"}:
            return False
        self._renderer.request_source_position(
            source_path, int(line), int(column)
        )
        return True

    def _edit_phrase_for_position(self, path: str, line: int, column: int) -> str:
        content = self._editor_panel.content_for_path(path)
        if content is None:
            return ""
        lines = content.splitlines()
        if not lines or int(line) < 1 or int(line) > len(lines):
            return ""
        raw = lines[int(line) - 1]
        if not raw.strip():
            return ""
        cursor_index = max(0, min(int(column) - 1, len(raw)))
        end = cursor_index
        while end < len(raw) and not raw[end].isspace():
            end += 1
        prefix = raw[:end]
        # Search visible prose, not LaTeX control syntax. Keep Unicode letters
        # and numbers so Persian and English phrases both work.
        prefix = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", prefix)
        prefix = prefix.replace("{", " ").replace("}", " ").replace("$", " ")
        words = re.findall(r"[^\W_]+(?:[’'‌-][^\W_]+)*", prefix, flags=re.UNICODE)
        if not words:
            return ""
        phrase = " ".join(words[-4:]).strip()
        return phrase if len(phrase) >= 2 else ""

    def _apply_pending_preview_edit_highlight(self) -> None:
        if not self._app_settings.preview_edit_location_highlight_enabled:
            target = ""
        else:
            target = self._pending_preview_edit_highlight
        if target == self._last_preview_edit_highlight:
            return
        self._last_preview_edit_highlight = target
        self._preview_panel.preview.set_edit_highlight(target)

    def _on_current_modification_changed(
        self,
        path: str,
        modified: bool,
    ) -> None:
        self._save_action.setEnabled(
            modified
        )

    def _on_navigator_path_renamed(
        self,
        old_path: str,
        new_path: str,
    ) -> None:
        self._search_window.rebuild_index()

        old_root = Path(old_path).resolve()
        new_root = Path(new_path).resolve()

        changed_references = PathReferenceUpdater.update_workspace_references(
            self._app_settings.search_default_path,
            old_root,
            new_root,
            ignore_file_path=self._app_settings.search_ignore_file_path,
        )
        updated_signatures: dict[Path, tuple[int, int]] = {}
        for signature_path, signature in self._file_signatures.items():
            try:
                relative = signature_path.relative_to(old_root)
            except ValueError:
                updated_signatures[signature_path] = signature
                continue
            updated_signatures[(new_root / relative).resolve()] = signature
        self._file_signatures = updated_signatures

        self._recent_file_paths = [
            (new_root / path.relative_to(old_root)).resolve()
            if self._is_same_or_child_path(path, old_root)
            else path
            for path in self._recent_file_paths
        ]

        self._editor_panel.rename_paths_under(
            old_path,
            new_path,
        )

        current = (
            self._editor_panel.current_path()
        )

        if current is not None:
            self._file_system_panel.select_path(
                current
            )

        for changed_path in changed_references:
            if self._editor_panel.content_for_path(changed_path) is None:
                continue
            try:
                changed_content = self._load_editor_file(changed_path)
            except (OSError, ValueError):
                continue
            self._editor_panel.replace_content_from_disk(
                changed_path,
                changed_content,
            )
            self._remember_file_signature(changed_path)

        if changed_references:
            self.statusBar().showMessage(
                f"Updated {len(changed_references)} path reference file(s) after move.",
                5000,
            )

        self._save_session()

    def _on_navigator_path_deleted(
        self,
        path: str,
    ) -> None:
        self._search_window.rebuild_index()

        deleted_root = Path(path).resolve()
        self._file_signatures = {
            candidate: signature
            for candidate, signature in self._file_signatures.items()
            if not self._is_same_or_child_path(
                candidate,
                deleted_root,
            )
        }
        self._recent_file_paths = [
            candidate
            for candidate in self._recent_file_paths
            if not self._is_same_or_child_path(
                candidate,
                deleted_root,
            )
        ]

        self._editor_panel.close_paths_under(
            path
        )

        current = (
            self._editor_panel.current_path()
        )

        if current is not None:
            self._file_system_panel.select_path(
                current
            )
        else:
            self._preview_panel.show_message(
                "Open a LaTeX or Markdown file to render its preview."
            )

        self._save_session()

    def _on_navigator_path_created(
        self,
        path: str,
    ) -> None:
        self._search_window.rebuild_index()

        created = Path(path)

        if (
            created.is_file()
            and created.suffix.lower()
            == ".tex"
        ):
            self._open_path(
                str(created)
            )
            return

        self._file_system_panel.select_path(
            created
        )
        self._save_session()

    def _migrate_legacy_qsettings_if_needed(self) -> None:
        """Copy the old Qt settings store into the persistent data folder once."""
        if self._session_settings.allKeys():
            return
        legacy = QSettings("nd_mind_mirror", "nd_mind_mirror_project")
        copied = False
        for key in legacy.allKeys():
            self._session_settings.setValue(key, legacy.value(key))
            copied = True
        if copied:
            self._session_settings.sync()

    def _restore_session(self) -> None:
        # Use explicit JSON values rather than Qt's opaque binary geometry.
        # A small config file is the primary store; QSettings remains a fallback
        # for compatibility with older releases.
        file_state = self._read_ui_state_file()
        rect_json = file_state.get(
            "window_rect",
            self._session_settings.value("ui/window_rect_json", ""),
        )
        if isinstance(rect_json, list):
            rect_json = json.dumps(rect_json)
        try:
            rect_values = json.loads(str(rect_json or ""))
            if (
                isinstance(rect_values, list)
                and len(rect_values) == 4
            ):
                x, y, width, height = [int(value) for value in rect_values]
                if width >= 400 and height >= 300:
                    self._deferred_window_rect = (x, y, width, height)
        except (TypeError, ValueError, json.JSONDecodeError):
            self._deferred_window_rect = None

        maximized_raw = file_state.get(
            "window_maximized",
            self._session_settings.value("ui/window_maximized", False),
        )
        if isinstance(maximized_raw, str):
            self._deferred_window_maximized = maximized_raw.strip().lower() in {
                "1", "true", "yes", "on"
            }
        else:
            self._deferred_window_maximized = bool(maximized_raw)

        self._deferred_main_splitter_sizes = self._coerce_saved_sizes(
            file_state.get(
                "main_splitter_sizes",
                self._session_settings.value("ui/main_splitter_sizes_json", ""),
            ),
            expected_count=3,
        )
        self._deferred_navigator_splitter_sizes = self._coerce_saved_sizes(
            file_state.get(
                "navigator_splitter_sizes",
                self._session_settings.value("ui/navigator_splitter_sizes_json", ""),
            ),
            expected_count=2,
        )

        expanded = self._session_settings.value(
            "filesystem/expanded_paths",
            [],
        )
        selected = self._session_settings.value(
            "filesystem/selected_path",
            "",
        )
        recent = self._session_settings.value(
            "editor/recent_files",
            [],
        )
        active = self._session_settings.value(
            "editor/active_file",
            "",
        )
        bookmarks_json = self._session_settings.value(
            "editor/bookmarks_json",
            "{}",
        )
        try:
            bookmarks = json.loads(str(bookmarks_json or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            bookmarks = {}
        self._editor_panel.set_bookmarks(bookmarks)

        view_states_json = self._session_settings.value(
            "editor/view_states_json",
            "{}",
        )
        try:
            view_states = json.loads(str(view_states_json or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            view_states = {}
        self._editor_panel.set_view_states(view_states)

        if isinstance(expanded, str):
            expanded = [expanded] if expanded else []

        if isinstance(recent, str):
            recent = [recent] if recent else []

        self._file_system_panel.restore_state(
            list(expanded),
            str(selected or ""),
        )

        valid_recent = []
        for path in list(recent)[-self._app_settings.editor_max_open_tabs:]:
            file_path = Path(str(path)).expanduser()
            if file_path.is_file():
                valid_recent.append(str(file_path.resolve()))

        for path in valid_recent:
            self._open_path(path, select=False)

        active_path: Path | None = None
        if active:
            if self._editor_panel.activate_path(str(active)):
                active_path = Path(str(active)).expanduser().resolve()
            elif valid_recent:
                fallback = Path(valid_recent[-1]).resolve()
                self._editor_panel.activate_path(fallback)
                active_path = fallback
        elif valid_recent:
            fallback = Path(valid_recent[-1]).resolve()
            self._editor_panel.activate_path(fallback)
            active_path = fallback

        # QFileSystemModel is populated asynchronously.  Re-reveal the active
        # restored tab after the model has had time to expose its ancestors so
        # the very first application launch state highlights the active file.
        if active_path is not None:
            for delay in (250, 800, 1800, 2800):
                QTimer.singleShot(
                    delay,
                    lambda item=active_path: self._file_system_panel.select_path(
                        item,
                        force_reveal=True,
                    ),
                )

    def _read_saved_sizes(
        self,
        key: str,
        expected_count: int,
    ) -> list[int] | None:
        return self._coerce_saved_sizes(
            self._session_settings.value(key, ""),
            expected_count,
        )

    @staticmethod
    def _coerce_saved_sizes(
        raw: object,
        expected_count: int,
    ) -> list[int] | None:
        values = raw
        if isinstance(values, str):
            try:
                values = json.loads(values or "")
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(values, list) or len(values) != expected_count:
            return None
        try:
            sizes = [max(int(value), 0) for value in values]
        except (TypeError, ValueError):
            return None
        if sum(sizes) <= 0:
            return None
        return sizes

    def _read_ui_state_file(self) -> dict[str, object]:
        try:
            raw = json.loads(self._ui_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_ui_state_file(self, state: dict[str, object]) -> None:
        try:
            self._ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._ui_state_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(state, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(self._ui_state_path)
        except OSError:
            # QSettings below remains a fallback if the config directory is
            # temporarily unavailable/read-only.
            pass

    def _schedule_ui_layout_save(self) -> None:
        if getattr(self, "_restoring_session", True):
            return
        timer = getattr(self, "_layout_save_timer", None)
        if timer is not None:
            timer.start()

    def _apply_deferred_ui_layout(self) -> None:
        if self._ui_layout_applied:
            return
        self._ui_layout_applied = True
        if self._deferred_window_rect is not None:
            x, y, width, height = self._deferred_window_rect
            candidate = QRect(x, y, width, height)
            screens = QApplication.screens()
            visible = any(
                screen.availableGeometry().intersects(candidate)
                for screen in screens
            )
            if visible:
                self.resize(candidate.width(), candidate.height())
                self.move(candidate.x(), candidate.y())
            elif screens:
                available = QApplication.primaryScreen().availableGeometry()
                width = min(width, available.width())
                height = min(height, available.height())
                self.resize(width, height)
                self.move(
                    available.x() + max((available.width() - width) // 2, 0),
                    available.y() + max((available.height() - height) // 2, 0),
                )

        if self._deferred_main_splitter_sizes is not None:
            self._splitter.setSizes(self._deferred_main_splitter_sizes)
        else:
            self._splitter.setSizes([320, 760, 480])

        if self._deferred_navigator_splitter_sizes is not None:
            self._navigator_splitter.setSizes(
                self._deferred_navigator_splitter_sizes
            )
        else:
            self._navigator_splitter.setSizes([560, 340])

        if self._deferred_window_maximized:
            self.showMaximized()

    def _save_ui_layout_state(self) -> None:
        if self._restoring_session:
            return

        rect = self.normalGeometry() if self.isMaximized() else self.geometry()
        self._session_settings.setValue(
            "ui/window_rect_json",
            json.dumps([rect.x(), rect.y(), rect.width(), rect.height()]),
        )
        self._session_settings.setValue(
            "ui/window_maximized",
            bool(self.isMaximized()),
        )
        self._session_settings.setValue(
            "ui/main_splitter_sizes_json",
            json.dumps(self._splitter.sizes()),
        )
        navigator_sizes = self._navigator_splitter.sizes()
        main_sizes = self._splitter.sizes()
        self._session_settings.setValue(
            "ui/navigator_splitter_sizes_json",
            json.dumps(navigator_sizes),
        )
        self._write_ui_state_file(
            {
                "window_rect": [
                    rect.x(), rect.y(), rect.width(), rect.height()
                ],
                "window_maximized": bool(self.isMaximized()),
                "main_splitter_sizes": main_sizes,
                "navigator_splitter_sizes": navigator_sizes,
            }
        )
        self._session_settings.sync()

    def _on_bookmarks_changed(self, data: object) -> None:
        if self._restoring_session:
            return
        self._session_settings.setValue(
            "editor/bookmarks_json",
            json.dumps(
                data if isinstance(data, dict) else self._editor_panel.bookmarks(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        self._session_settings.sync()
        self._refresh_bookmarks_menu()

    def _refresh_bookmarks_menu(self) -> None:
        if not hasattr(self, "_bookmarks_menu"):
            return
        self._bookmarks_menu.clear()
        self._bookmarks_menu.addAction(self._toggle_bookmark_action)
        data = self._editor_panel.bookmarks()
        entries: list[tuple[str, int, int, str, str]] = []
        for raw_path, bookmarks in data.items():
            for bookmark in bookmarks:
                try:
                    line = max(int(bookmark.get("line", 1)), 1)
                except (TypeError, ValueError):
                    line = 1
                try:
                    column = max(int(bookmark.get("column", 1)), 1)
                except (TypeError, ValueError):
                    column = 1
                name = str(bookmark.get("name", "")).strip()
                anchor = str(bookmark.get("anchor", "")).strip()
                label = name or anchor[:48] or f"Line {line}"
                entries.append(
                    (str(raw_path), line, column, label, Path(str(raw_path)).name)
                )
        if not entries:
            empty = self._bookmarks_menu.addAction("No bookmarks")
            empty.setEnabled(False)
            return
        self._bookmarks_menu.addSeparator()
        for raw_path, line, column, label, filename in sorted(
            entries, key=lambda item: (item[0].casefold(), item[1], item[2])
        ):
            action = self._bookmarks_menu.addAction(
                f"{label} — {filename}:{line}:{column}"
            )
            action.setToolTip(raw_path)
            action.triggered.connect(
                lambda checked=False, path=raw_path, target=line, col=column: self._activate_bookmark(
                    path, target, col
                )
            )

    def _activate_bookmark(
        self, path: str, line: int, column: int = 1
    ) -> None:
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            self._show_warning(f"Bookmarked file does not exist: {file_path}")
            return
        self._open_path(str(file_path), select=True, reveal_in_navigator=True)
        QTimer.singleShot(
            0,
            lambda target=int(line), col=int(column): self._editor_panel.go_to_location(
                target, col
            ),
        )

    def _save_session(self) -> None:
        if self._restoring_session:
            return

        self._save_ui_layout_state()
        self._session_settings.setValue(
            "filesystem/expanded_paths",
            self._file_system_panel.expanded_paths(),
        )
        self._session_settings.setValue(
            "filesystem/selected_path",
            self._file_system_panel.selected_path(),
        )
        self._session_settings.setValue(
            "editor/recent_files",
            [
                str(path)
                for path in self._recent_file_paths
                if path in self._editor_panel.open_paths()
            ],
        )
        current = (
            self._editor_panel.current_path()
        )

        self._session_settings.setValue(
            "editor/active_file",
            (
                str(current)
                if current is not None
                else ""
            ),
        )
        self._session_settings.setValue(
            "editor/view_states_json",
            json.dumps(
                self._editor_panel.view_states(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        self._session_settings.setValue(
            "editor/bookmarks_json",
            json.dumps(
                self._editor_panel.bookmarks(),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        self._session_settings.sync()

    def _save_all_modified(
        self,
    ) -> bool:
        documents = (
            self._editor_panel.modified_documents()
        )

        for (
            path,
            content,
        ) in documents:
            if not self._save_document(
                path,
                content,
                show_error=True,
            ):
                return False

            self._editor_panel.mark_saved(
                path
            )

        return True

    def _is_same_or_child_path(
        self,
        candidate: Path,
        parent: Path,
    ) -> bool:
        if candidate == parent:
            return True
        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False

    def _show_warning(
        self,
        message: str,
    ) -> None:
        QMessageBox.warning(
            self,
            "nd_mind_mirror_project",
            message,
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._ui_layout_applied:
            # Window managers can adjust the frame during mapping. Restoring a
            # moment after show makes width/height and all splitter columns
            # deterministic on both X11 and Wayland.
            QTimer.singleShot(80, self._apply_deferred_ui_layout)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_ui_layout_save()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._schedule_ui_layout_save()

    def closeEvent(self, event) -> None:
        modified = (
            self._editor_panel.modified_documents()
        )

        if modified:
            names = "\n".join(
                f"• {path.name}"
                for path, _ in modified
            )

            decision = QMessageBox.question(
                self,
                "Unsaved files",
                "These files have unsaved changes:\n\n"
                f"{names}\n\nSave them before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )

            if (
                decision
                == QMessageBox.StandardButton.Cancel
            ):
                event.ignore()
                return

            if (
                decision
                == QMessageBox.StandardButton.Save
                and not self._save_all_modified()
            ):
                event.ignore()
                return

        self._autosave_timer.stop()
        self._external_file_sync_timer.stop()
        self._recent_file_switcher.dismiss()
        self._search_window.close()
        self._save_session()
        event.accept()
