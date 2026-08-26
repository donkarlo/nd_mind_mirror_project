"""Keep Navigator interactions stable and make Preview highlighting selection-only."""

from __future__ import annotations

from pathlib import Path
from types import MethodType

from PySide6.QtCore import QItemSelectionModel, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMenu


class WorkspaceInteractionController:
    """Coordinate Navigator selection, path remapping, and lightweight Preview sync."""

    _INDEX_RETRY_DELAYS_MS = (0, 20, 50, 100, 180, 300)

    def __init__(self, main_window) -> None:
        self._window = main_window
        self._panel = main_window._file_system_panel
        self._tree = self._panel._tree
        self._renderer = main_window._renderer
        self._editor_panel = main_window._editor_panel
        self._preview = main_window._preview_panel.preview
        self._context_controller = getattr(main_window, "_navigator_context_controller", None)
        self._navigator_selection_generation = 0
        # Compatibility handle only. LateRuntimeFixes still references this
        # timer during construction; the performance cleanup disables it.
        self._highlight_timer = QTimer(main_window)
        self._highlight_timer.setSingleShot(True)

        self._install_fast_navigator_selection()
        self._install_context_menu()
        self._install_path_remap_guard()
        self._install_selection_only_preview_sync()

    def _install_fast_navigator_selection(self) -> None:
        controller = self

        def select_path(panel, path: str | Path, *, force_reveal: bool = False) -> None:
            target = Path(path).expanduser().resolve()
            if not panel._is_same_or_child(target, panel._root_path):
                return

            current = panel.selected_path()
            if current and not force_reveal:
                try:
                    if Path(current).expanduser().resolve() == target:
                        panel._pending_reveal = None
                        return
                except OSError:
                    pass

            controller._navigator_selection_generation += 1
            generation = controller._navigator_selection_generation
            panel._pending_reveal = target
            controller._select_index_when_available(target, generation, retry_index=0)

        self._panel.select_path = MethodType(select_path, self._panel)

    def _select_index_when_available(
        self,
        target: Path,
        generation: int,
        retry_index: int,
    ) -> None:
        if generation != self._navigator_selection_generation:
            return
        if not self._panel._is_same_or_child(target, self._panel._root_path):
            return

        index = self._panel._view_index_for_path(target)
        if not index.isValid():
            next_retry = retry_index + 1
            if next_retry >= len(self._INDEX_RETRY_DELAYS_MS):
                self._panel._pending_reveal = None
                return
            delay = self._INDEX_RETRY_DELAYS_MS[next_retry]
            QTimer.singleShot(
                delay,
                lambda item=target, token=generation, attempt=next_retry:
                self._select_index_when_available(item, token, attempt),
            )
            return

        ancestors = []
        parent_index = index.parent()
        while parent_index.isValid():
            ancestors.append(parent_index)
            parent_path = self._panel._path_for_view_index(parent_index)
            if parent_path and Path(parent_path) == self._panel._root_path:
                break
            parent_index = parent_index.parent()

        for ancestor_index in reversed(ancestors):
            self._tree.expand(ancestor_index)
            ancestor_path = self._panel._path_for_view_index(ancestor_index)
            if ancestor_path:
                self._panel._expanded_paths.add(ancestor_path)

        selection_model = self._tree.selectionModel()
        if selection_model is not None:
            flags = (
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(index, flags)

        self._tree.setCurrentIndex(index)
        self._tree.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        self._panel._pending_reveal = None

    def _install_context_menu(self) -> None:
        if self._context_controller is None:
            return
        try:
            self._tree.customContextMenuRequested.disconnect(
                self._context_controller.show_menu
            )
        except (RuntimeError, TypeError):
            pass
        self._tree.customContextMenuRequested.connect(self._show_navigator_menu)

    def _show_navigator_menu(self, position) -> None:
        index = self._tree.indexAt(position)
        if not index.isValid():
            return

        self._tree.setCurrentIndex(index)
        path = Path(self._panel._path_for_view_index(index))
        menu = QMenu(self._panel)
        open_menu = menu.addMenu("Open")
        copy_menu = menu.addMenu("Copy / Share")
        create_menu = menu.addMenu("Create")
        manage_menu = menu.addMenu("Manage")

        open_files = open_menu.addAction("Open in Files")
        open_files.triggered.connect(
            lambda _checked=False: self._panel._open_in_file_manager(path)
        )

        managed_graphic = (
            path.suffix.lower() == ".ndgraphic"
            or (
                path.suffix.lower() == ".png"
                and path.with_suffix(".ndgraphic").is_file()
            )
        )
        if managed_graphic:
            edit_ipad = open_menu.addAction("Edit image in iPad…")
            edit_ipad.triggered.connect(
                lambda _checked=False: self._panel.graphic_edit_requested.emit(
                    str(path.expanduser().resolve())
                )
            )

        pin_callback = getattr(self._context_controller, "_pin_callback", None)
        if path.is_file() and pin_callback is not None:
            pin_action = open_menu.addAction("Pin File in Tabs")
            pin_action.triggered.connect(
                lambda _checked=False: pin_callback(path)
            )

        copy_absolute = copy_menu.addAction("Copy Absolute Path")
        copy_absolute.triggered.connect(
            lambda _checked=False: QApplication.clipboard().setText(
                str(path.expanduser().resolve())
            )
        )

        dropbox_path = self._dropbox_path(path)
        copy_dropbox = copy_menu.addAction("Copy Dropbox Path")
        copy_dropbox.setEnabled(bool(dropbox_path))
        copy_dropbox.triggered.connect(
            lambda _checked=False, value=dropbox_path:
            QApplication.clipboard().setText(value)
        )

        copy_name = copy_menu.addAction("Copy File Name")
        copy_name.triggered.connect(
            lambda _checked=False: QApplication.clipboard().setText(path.name)
        )

        github_url = self._context_controller._github_url(path)
        copy_github = copy_menu.addAction("Copy GitHub URL")
        open_github = copy_menu.addAction("Open GitHub URL")
        copy_github.setEnabled(bool(github_url))
        open_github.setEnabled(bool(github_url))
        copy_github.triggered.connect(
            lambda _checked=False, value=github_url:
            QApplication.clipboard().setText(value)
        )
        open_github.triggered.connect(
            lambda _checked=False, value=github_url:
            QDesktopServices.openUrl(QUrl(value))
        )

        paste_image = create_menu.addAction("Paste Clipboard Image Here")
        paste_image.triggered.connect(
            lambda _checked=False: self._panel._save_current_clipboard_image(
                self._panel._target_directory(path),
                one_shot=False,
            )
        )
        new_latex = create_menu.addAction("New LaTeX File…")
        new_latex.triggered.connect(
            lambda _checked=False: self._panel._create_file(path, latex=True)
        )
        new_file = create_menu.addAction("New File…")
        new_file.triggered.connect(
            lambda _checked=False: self._panel._create_file(path, latex=False)
        )
        new_folder = create_menu.addAction("New Folder…")
        new_folder.triggered.connect(
            lambda _checked=False: self._panel._create_folder(path)
        )

        rename = manage_menu.addAction("Rename…")
        delete = manage_menu.addAction("Delete…")
        rename.setEnabled(path != self._panel._root_path)
        delete.setEnabled(path != self._panel._root_path)
        rename.triggered.connect(
            lambda _checked=False: self._panel._rename_path(path)
        )
        delete.triggered.connect(
            lambda _checked=False: self._panel._delete_path(path)
        )

        menu.exec(self._tree.viewport().mapToGlobal(position))

    @staticmethod
    def _dropbox_path(path: Path) -> str:
        try:
            relative = path.expanduser().resolve().relative_to(
                (Path.home() / "Dropbox").resolve()
            )
        except (OSError, ValueError):
            return ""
        return "/" + relative.as_posix()

    def _install_path_remap_guard(self) -> None:
        self._panel.path_about_to_move.connect(self._before_path_move)
        self._panel.path_renamed.connect(self._after_path_renamed)

    def _before_path_move(self, _old_path: str) -> None:
        for timer_name in ("_timer", "_sync_timer"):
            timer = getattr(self._renderer, timer_name, None)
            if timer is not None:
                try:
                    timer.stop()
                except RuntimeError:
                    pass
        stop_process = getattr(self._renderer, "_stop_running_process", None)
        if callable(stop_process):
            try:
                stop_process()
            except RuntimeError:
                pass

    def _after_path_renamed(self, old_path: str, new_path: str) -> None:
        old_root = Path(old_path).expanduser().resolve()
        new_root = Path(new_path).expanduser().resolve()
        for attribute in (
            "_source_path",
            "_pending_source_path",
            "_cache_source_path",
            "_pending_sync_source_path",
            "_working_directory",
        ):
            value = getattr(self._renderer, attribute, None)
            updated = self._remap_path(value, old_root, new_root)
            if updated is not None:
                setattr(self._renderer, attribute, updated)

        QTimer.singleShot(0, self._render_current_path_after_move)

    @staticmethod
    def _remap_path(value, old_root: Path, new_root: Path) -> Path | None:
        if value is None:
            return None
        try:
            candidate = Path(value).expanduser().resolve()
            relative = candidate.relative_to(old_root)
        except (OSError, TypeError, ValueError):
            return None
        return (new_root / relative).resolve()

    def _render_current_path_after_move(self) -> None:
        path = self._editor_panel.current_path()
        editor = self._editor_panel.current_editor()
        if path is None or editor is None:
            return
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() not in {".tex", ".tikz"} or not path.is_file():
            return
        try:
            source = editor.toPlainText()
        except AttributeError:
            return
        self._renderer.render(source, source_path=path, immediate=True)

    def _install_selection_only_preview_sync(self) -> None:
        """Do not start SyncTeX/search work for a plain caret or editor scrolling."""
        try:
            self._editor_panel.current_cursor_changed.disconnect(
                self._window._on_current_cursor_changed
            )
        except (RuntimeError, TypeError):
            pass
        try:
            self._editor_panel.current_view_changed.disconnect(
                self._window._on_current_view_changed
            )
        except (RuntimeError, TypeError):
            pass

        self._editor_panel.current_cursor_changed.connect(
            self._on_editor_cursor_changed
        )
        self._editor_panel.current_view_changed.connect(
            self._on_editor_view_changed
        )
        self._set_preview_highlight_text("")

    def _selection_highlight_text(self) -> str:
        editor = self._editor_panel.current_editor()
        if editor is None:
            return ""
        try:
            visual = str(getattr(editor, "edit_mode", "source")) == "visual"
            cursor = editor._visual_editor.textCursor() if visual else editor.textCursor()
            if not cursor.hasSelection():
                return ""
            text = cursor.selectedText().replace("\u2029", " ").strip()
            if not visual:
                text = editor._preview_visible_source_text(text)
            return editor._normalize_preview_target(text)[:180]
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return ""

    def _on_editor_cursor_changed(self, path: str, line: int, column: int) -> None:
        try:
            self._window._structure_panel.set_current_line(int(line))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

        text = self._selection_highlight_text()
        self._set_preview_highlight_text(text)
        if not text:
            return

        try:
            self._window._request_preview_source_position(path, line, column)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def _on_editor_view_changed(self, _path: str, _line: int, _column: int) -> None:
        """Editor scrolling must not trigger SyncTeX, PDF search, or full rehighlight."""
        return

    def _update_preview_selection_highlight(self) -> None:
        self._set_preview_highlight_text(self._selection_highlight_text())

    def _sync_preview_highlight(self) -> None:
        self._update_preview_selection_highlight()

    def _set_preview_highlight_text(self, text: str) -> None:
        try:
            self._preview.set_edit_highlight(str(text or ""))
        except (AttributeError, RuntimeError):
            pass
