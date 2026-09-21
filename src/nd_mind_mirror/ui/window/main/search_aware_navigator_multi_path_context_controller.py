"""Extend the canonical Navigator context menu with scoped workspace search."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from nd_mind_mirror.core.clipboard.file_clipboard_mime_data_controller import (
    FileClipboardMimeDataController,
)
from nd_mind_mirror.ui.window.main.navigator_multi_path_context_controller import (
    NavigatorMultiPathContextController,
)


class SearchAwareNavigatorMultiPathContextController(
    NavigatorMultiPathContextController
):
    """Keep multi-path/search behavior and make file clipboard ownership explicit."""

    def __init__(
        self,
        file_system_panel,
        pin_callback=None,
        file_search_callback=None,
        text_search_callback=None,
    ) -> None:
        """Initialize Navigator multi-path behavior with scoped search callbacks."""
        self._file_search_callback = file_search_callback
        self._text_search_callback = text_search_callback
        super().__init__(file_system_panel, pin_callback)

        self._file_clipboard_mime = FileClipboardMimeDataController(
            QApplication.clipboard()
        )
        self._file_clipboard_mime.clipboard.dataChanged.connect(
            self._on_system_clipboard_changed
        )

    @classmethod
    def replace(
        cls,
        existing,
        file_system_panel,
        pin_callback=None,
        file_search_callback=None,
        text_search_callback=None,
    ) -> "SearchAwareNavigatorMultiPathContextController":
        """Replace the pre-multi controller exactly once during window composition."""
        if existing is not None:
            try:
                file_system_panel._tree.customContextMenuRequested.disconnect(
                    existing.show_menu
                )
            except (RuntimeError, TypeError):
                pass

            for name in (
                "_copy_shortcut",
                "_cut_shortcut",
                "_paste_shortcut",
            ):
                shortcut = getattr(existing, name, None)
                if shortcut is None:
                    continue
                try:
                    shortcut.setEnabled(False)
                    shortcut.deleteLater()
                except RuntimeError:
                    pass

        return cls(
            file_system_panel,
            pin_callback=pin_callback,
            file_search_callback=file_search_callback,
            text_search_callback=text_search_callback,
        )

    def _store_selection(self, mode: str) -> None:
        """Publish the selected files as the active OS clipboard payload."""
        paths = self.selected_paths()
        if not paths:
            return

        self._clipboard_paths = paths
        self._clipboard_mode = mode
        self._file_clipboard_mime.publish_paths(paths)

        action = "Copied" if mode == "copy" else "Cut"
        self._panel.window().statusBar().showMessage(
            f"{action} {len(paths)} Navigator item(s).",
            2500,
        )

    def _on_system_clipboard_changed(self) -> None:
        """Drop stale internal sources when another application owns clipboard data."""
        mime_data = self._file_clipboard_mime.clipboard.mimeData()
        if FileClipboardMimeDataController.is_mind_mirror_file_payload(
            mime_data
        ):
            return
        self._clipboard_paths = []
        self._clipboard_mode = ""

    def _clipboard_sources_and_mode(self) -> tuple[list[Path], str]:
        """Prefer live internal paths, otherwise import standard OS file URLs."""
        internal = self._existing_clipboard_paths()
        if internal:
            return internal, self._clipboard_mode or "copy"

        external = FileClipboardMimeDataController.local_paths(
            self._file_clipboard_mime.clipboard.mimeData()
        )
        return self._top_level_paths(external), "copy"

    def can_paste(self) -> bool:
        """Accept internal Navigator sources and local files copied in other apps."""
        sources, _mode = self._clipboard_sources_and_mode()
        return bool(sources)

    def paste_into_path(self, path: Path) -> None:
        """Paste internal or OS file clipboard sources without image fallback."""
        sources, mode = self._clipboard_sources_and_mode()
        if not sources:
            return

        try:
            destination = (
                self._panel
                ._target_directory(path)
                .expanduser()
                .resolve()
            )
        except OSError as exc:
            QMessageBox.warning(
                self._panel,
                "Paste",
                str(exc),
            )
            return

        if not destination.is_dir():
            QMessageBox.warning(
                self._panel,
                "Paste",
                "The paste destination is not a folder.",
            )
            return

        mappings = self._destination_mappings(
            sources,
            destination,
        )
        if mappings is None:
            return

        if mode == "cut":
            self._paste_cut(mappings)
            return
        self._paste_copy(mappings)

    def show_menu(self, position) -> None:
        """Show the canonical menu plus folder-scoped file and text searches."""
        index = self._tree.indexAt(position)
        if not index.isValid():
            return

        raw_path = self._panel._path_for_view_index(index)
        if not raw_path:
            return
        path = Path(raw_path).expanduser()
        self._prepare_context_selection(index)
        selected_paths = self.selected_paths()

        menu = QMenu(self._panel)

        copy_item = menu.addAction("Copy\tCtrl+C")
        copy_item.setEnabled(bool(selected_paths))
        copy_item.triggered.connect(self.copy_selected_path)

        cut_item = menu.addAction("Cut\tCtrl+X")
        cut_item.setEnabled(bool(selected_paths))
        cut_item.triggered.connect(self.cut_selected_paths)

        paste_item = menu.addAction("Paste\tCtrl+V")
        paste_item.setEnabled(self.can_paste())
        paste_item.triggered.connect(lambda: self.paste_into_path(path))
        menu.addSeparator()

        if path.is_dir():
            search_menu = menu.addMenu("Search")
            search_files = search_menu.addAction("Search Files / Folders Here")
            search_files.setEnabled(callable(self._file_search_callback))
            if callable(self._file_search_callback):
                search_files.triggered.connect(
                    lambda: self._file_search_callback(path)
                )

            search_text = search_menu.addAction("Search Text in Files Here")
            search_text.setEnabled(callable(self._text_search_callback))
            if callable(self._text_search_callback):
                search_text.triggered.connect(
                    lambda: self._text_search_callback(path)
                )

        open_menu = menu.addMenu("Open")
        copy_menu = menu.addMenu("Copy / Share")
        create_menu = menu.addMenu("Create")
        manage_menu = menu.addMenu("Manage")

        open_files = open_menu.addAction("Open in Files")
        open_files.triggered.connect(
            lambda: self._panel._open_in_file_manager(path)
        )

        if self._is_ipad_editable(path):
            edit_ipad = open_menu.addAction("Edit image in iPad…")
            edit_ipad.triggered.connect(
                lambda: self._panel.graphic_edit_requested.emit(
                    str(path.expanduser().resolve())
                )
            )

        if path.is_file() and self._pin_callback is not None:
            pin_action = open_menu.addAction("Pin File in Tabs")
            pin_action.triggered.connect(lambda: self._pin_callback(path))

        copy_path = copy_menu.addAction("Copy Absolute Path")
        copy_path.triggered.connect(self._copy_selected_absolute_paths)

        copy_default_path = copy_menu.addAction("Copy from Default Path")
        copy_default_path.setEnabled(bool(self._selected_default_rooted_paths()))
        copy_default_path.triggered.connect(
            self._copy_selected_default_rooted_paths
        )

        copy_name = copy_menu.addAction("Copy File Name")
        copy_name.triggered.connect(self._copy_selected_names)

        github_url = self._github_url(path)
        copy_github = copy_menu.addAction("Copy GitHub URL")
        open_github = copy_menu.addAction("Open GitHub URL")
        copy_github.setEnabled(bool(github_url))
        open_github.setEnabled(bool(github_url))
        copy_github.triggered.connect(
            lambda: QApplication.clipboard().setText(github_url)
        )
        open_github.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(github_url))
        )

        paste_image = create_menu.addAction("Paste Clipboard Image Here")
        paste_image.triggered.connect(
            lambda: self._panel._save_current_clipboard_image(
                self._panel._target_directory(path),
                one_shot=False,
            )
        )
        new_latex = create_menu.addAction("New LaTeX File…")
        new_latex.triggered.connect(
            lambda: self._panel._create_file(path, latex=True)
        )
        new_file = create_menu.addAction("New File…")
        new_file.triggered.connect(
            lambda: self._panel._create_file(path, latex=False)
        )
        new_folder = create_menu.addAction("New Folder…")
        new_folder.triggered.connect(lambda: self._panel._create_folder(path))

        rename = manage_menu.addAction("Rename…")
        delete = manage_menu.addAction("Delete…")
        single_selection = len(selected_paths) == 1
        rename.setEnabled(single_selection and path != self._panel._root_path)
        delete.setEnabled(bool(selected_paths))
        rename.triggered.connect(lambda: self._panel._rename_path(path))
        if len(selected_paths) > 1:
            delete.triggered.connect(self._panel._delete_selected_path)
        else:
            delete.triggered.connect(lambda: self._panel._delete_path(path))

        try:
            menu.exec(self._tree.viewport().mapToGlobal(position))
        finally:
            # Context-menu actions are intentionally ephemeral.  Registering
            # QAction shortcuts here would create window-wide Ctrl+C/X/V
            # owners that can steal native text editing shortcuts in Source.
            menu.deleteLater()
