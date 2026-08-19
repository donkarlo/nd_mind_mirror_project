from pathlib import Path
import shutil

from PySide6.QtCore import (
    QSettings,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
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
from nd_mind_mirror.ui.input.double_shift.double_shift_event_filter import (
    DoubleShiftEventFilter,
)
from nd_mind_mirror.ui.input.ctrl_tab.ctrl_tab_event_filter import (
    CtrlTabEventFilter,
)
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel
from nd_mind_mirror.ui.panel.file_system.file_system_panel import (
    FileSystemPanel,
)
from nd_mind_mirror.ui.panel.preview.preview_panel import PreviewPanel
from nd_mind_mirror.ui.search.window.search_window import SearchWindow
from nd_mind_mirror.ui.switcher.recent_file.recent_file_switcher import (
    RecentFileSwitcher,
)
from nd_mind_mirror.ui.window.base.window import Window


class MainWindow(Window):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "nd_mind_mirror_project"
        )
        self.resize(1500, 900)

        self._restoring_session = True
        self._session_settings = QSettings(
            "nd_mind_mirror",
            "nd_mind_mirror_project",
        )
        self._app_settings = YamlSettings()
        self._file_signatures: dict[Path, tuple[int, int]] = {}
        self._recent_file_paths: list[Path] = []

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
        )

        self._editor_panel = EditorPanel(
            completions=completions,
            app_settings=self._app_settings,
            parent=self,
        )
        self._preview_panel = PreviewPanel(
            self
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
            self._file_system_panel
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

        self._create_actions()
        self._connect_signals()
        self._configure_autosave()
        self._configure_external_file_sync()
        self._restore_session()

        self._restoring_session = False

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
            self._search_action
        )

        settings_menu = self.menuBar().addMenu(
            "Settings"
        )
        settings_menu.addAction(
            self._edit_settings_action
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
        self._file_system_panel.path_renamed.connect(
            self._on_navigator_path_renamed
        )
        self._file_system_panel.path_deleted.connect(
            self._on_navigator_path_deleted
        )
        self._file_system_panel.path_created.connect(
            self._on_navigator_path_created
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
        self._editor_panel.capacity_reached.connect(
            self._show_warning
        )
        self._editor_panel.tab_close_requested.connect(
            self._handle_tab_close_request
        )

        self._preview_panel.export_requested.connect(
            self._export_pdf
        )

        self._renderer.rendered.connect(
            self._preview_panel.preview.show_pdf
        )
        self._renderer.failed.connect(
            self._preview_panel.preview.show_error
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
            self._save_session()
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
            "Editable files (*.tex *.yaml *.yml);;LaTeX files (*.tex);;YAML files (*.yaml *.yml);;All files (*)",
        )

        if path:
            self._open_path(path)

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

    def _load_editor_file(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()

        if suffix == ".tex":
            return self._document.load(file_path)

        if suffix in {".yaml", ".yml"}:
            try:
                return file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return file_path.read_text(encoding="latin-1")

        raise ValueError(
            "Only .tex, .yaml, and .yml files can be opened in the editor."
        )

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

        if path.resolve() == self._app_settings.settings_path.resolve():
            self._reload_yaml_settings()

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

                if path.resolve() == self._app_settings.settings_path.resolve():
                    self._reload_yaml_settings()

                self.statusBar().showMessage(
                    f"Reloaded external change: {path}",
                    3500,
                )

            self._file_signatures[path] = signature

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
        )
        self._double_shift_filter.set_interval_ms(
            self._app_settings.double_shift_interval_ms
        )
        self._splitter.setHandleWidth(
            self._app_settings.splitter_handle_width
        )
        self._configure_autosave()
        self._configure_external_file_sync()

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
            Path(path).suffix.lower() == ".tex"
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

        if file_path.suffix.lower() == ".tex":
            self._preview_panel.preview.set_source_document(
                file_path
            )

        if file_path.suffix.lower() != ".tex":
            if file_path.resolve() == self._app_settings.settings_path.resolve():
                self._preview_panel.preview.show_message(
                    "settings.yaml is open in the editor. Save it to apply "
                    "the new settings immediately."
                )
            else:
                self._preview_panel.preview.show_message(
                    f"No LaTeX preview for {file_path.name}."
                )
            return

        self._renderer.render(
            content,
            source_path=file_path,
            immediate=immediate,
        )

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
            self._preview_panel.preview.show_message(
                "Open a .tex file to render its preview."
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

    def _restore_session(self) -> None:
        splitter_state = (
            self._session_settings.value(
                "ui/splitter_state"
            )
        )

        if splitter_state is not None:
            restored = self._splitter.restoreState(
                splitter_state
            )
        else:
            restored = False

        if not restored:
            self._splitter.setSizes(
                [320, 760, 480]
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

        if isinstance(expanded, str):
            expanded = (
                [expanded]
                if expanded
                else []
            )

        if isinstance(recent, str):
            recent = (
                [recent]
                if recent
                else []
            )

        self._file_system_panel.restore_state(
            list(expanded),
            str(selected or ""),
        )

        valid_recent = []

        for path in list(
            recent
        )[-10:]:
            file_path = Path(
                str(path)
            ).expanduser()

            if file_path.is_file():
                valid_recent.append(
                    str(
                        file_path.resolve()
                    )
                )

        for path in valid_recent:
            self._open_path(
                path,
                select=False,
            )

        if active:
            if not self._editor_panel.activate_path(
                str(active)
            ):
                if valid_recent:
                    self._editor_panel.activate_path(
                        valid_recent[-1]
                    )
        elif valid_recent:
            self._editor_panel.activate_path(
                valid_recent[-1]
            )

    def _save_session(self) -> None:
        if self._restoring_session:
            return

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
        self._session_settings.setValue(
            "ui/splitter_state",
            self._splitter.saveState(),
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
