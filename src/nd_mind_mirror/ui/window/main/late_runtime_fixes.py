"""Apply focused runtime fixes that are safer as additive hooks than rewrites of large editors."""

from __future__ import annotations

import ctypes
import gc
from pathlib import Path
from types import MethodType
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.window.main.main_window import MainWindow


class _DeleteDialogFocusFilter(QObject):
    """Make the destructive confirmation keyboard-friendly without changing the dialog workflow."""

    def eventFilter(self, watched, event) -> bool:
        if (
            isinstance(watched, QMessageBox)
            and event.type() in {QEvent.Type.Show, QEvent.Type.ShowToParent}
            and watched.windowTitle().strip().casefold() == "delete"
        ):
            yes_button = watched.button(QMessageBox.StandardButton.Yes)
            if yes_button is not None:
                watched.setDefaultButton(QMessageBox.StandardButton.Yes)
                QTimer.singleShot(0, yes_button.setFocus)
        return super().eventFilter(watched, event)


class _IdleMemoryCompactor(QObject):
    """Return unused Python/glibc heap pages periodically while leaving every feature enabled."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(180_000)
        self._timer.timeout.connect(self.compact)
        self._timer.start()
        QTimer.singleShot(30_000, self.compact)

    def compact(self) -> None:
        app = QApplication.instance()
        if app is not None and app.activeModalWidget() is not None:
            return
        gc.collect()
        try:
            libc = ctypes.CDLL(None)
            malloc_trim = getattr(libc, "malloc_trim", None)
            if malloc_trim is not None:
                malloc_trim(0)
        except (OSError, AttributeError):
            pass


class LateRuntimeFixes:
    """Install bookmark, Visual paste, delete-focus, sticky-highlight, and memory fixes."""

    _class_patches_installed = False
    _original_visual_insert_from_mime: Callable | None = None
    _original_activate_bookmark: Callable | None = None

    @classmethod
    def install_class_patches(cls) -> None:
        if cls._class_patches_installed:
            return
        cls._install_visual_clipboard_image_paste()
        cls._install_bookmark_navigation_retry()
        cls._class_patches_installed = True

    @classmethod
    def _install_visual_clipboard_image_paste(cls) -> None:
        """Route image paste from Visual through LatexEditor's existing managed-image insertion."""
        original = LatexVisualEditor.insertFromMimeData
        cls._original_visual_insert_from_mime = original

        def insert_from_mime_data(editor: LatexVisualEditor, source) -> None:
            owner = editor.parentWidget()
            has_image = bool(getattr(source, "hasImage", lambda: False)())
            if not has_image or not isinstance(owner, LatexEditor):
                original(editor, source)
                return

            try:
                line, column = editor.current_source_location()
            except (AttributeError, RuntimeError, TypeError, ValueError):
                line, column = 1, 1

            owner._go_to_source_location(
                max(int(line), 1),
                max(int(column), 1),
                align_top=False,
            )
            LatexEditor.insertFromMimeData(owner, source)
            owner._visual_dirty = True
            owner._refresh_visual_projection()
            try:
                editor.go_to_source_location(
                    max(int(line), 1),
                    max(int(column), 1),
                    align_top=False,
                )
            except (AttributeError, RuntimeError):
                pass
            editor.setFocus()

        LatexVisualEditor.insertFromMimeData = insert_from_mime_data

    @classmethod
    def _install_bookmark_navigation_retry(cls) -> None:
        """Wait until an asynchronously opened bookmark tab is active before moving its cursor."""
        original = MainWindow._activate_bookmark
        cls._original_activate_bookmark = original

        def activate_bookmark(window: MainWindow, path: str, line: int, column: int = 1) -> None:
            file_path = Path(path).expanduser().resolve()
            if not file_path.is_file():
                window._show_warning(f"Bookmarked file does not exist: {file_path}")
                return

            window._open_path(str(file_path), select=True, reveal_in_navigator=True)
            target_line = max(int(line), 1)
            target_column = max(int(column), 1)
            attempts = (0, 20, 50, 100, 180, 300)

            def try_go(index: int = 0) -> None:
                current = window._editor_panel.current_path()
                editor = window._editor_panel.current_editor()
                current_path = None
                if current is not None:
                    try:
                        current_path = Path(current).expanduser().resolve()
                    except OSError:
                        current_path = None

                if editor is not None and current_path == file_path:
                    window._editor_panel.go_to_location(target_line, target_column)
                    return

                next_index = index + 1
                if next_index < len(attempts):
                    QTimer.singleShot(
                        attempts[next_index],
                        lambda attempt=next_index: try_go(attempt),
                    )

            QTimer.singleShot(0, try_go)

        MainWindow._activate_bookmark = activate_bookmark

    @staticmethod
    def install_application(application: QApplication) -> list[QObject]:
        """Install the delete-dialog focus filter and idle heap compactor."""
        delete_filter = _DeleteDialogFocusFilter(application)
        application.installEventFilter(delete_filter)
        compactor = _IdleMemoryCompactor(application)
        return [delete_filter, compactor]

    @staticmethod
    def install_window(window) -> object | None:
        """Keep the last non-empty edit selection highlighted across Source/Visual/Preview switches."""
        controller = getattr(window, "_workspace_interaction_controller", None)
        if controller is None:
            return None

        original = controller._set_preview_highlight_text
        sticky_state = {"text": str(getattr(controller, "_last_highlight_text", "") or "")}

        def sticky_set_preview_highlight_text(_controller, text: str) -> None:
            value = str(text or "")
            if value.strip():
                sticky_state["text"] = value
                original(value)
                return
            if sticky_state["text"]:
                return
            original("")

        controller._set_preview_highlight_text = MethodType(
            sticky_set_preview_highlight_text,
            controller,
        )

        tree = window._file_system_panel._tree
        move_timer = QTimer(window)
        move_timer.setSingleShot(True)
        move_timer.setInterval(45)

        def freeze_tree(*_args) -> None:
            tree.setUpdatesEnabled(False)
            move_timer.setInterval(500)
            move_timer.start()

        def unfreeze_tree(*_args) -> None:
            move_timer.setInterval(45)
            move_timer.start()

        def apply_unfreeze() -> None:
            tree.setUpdatesEnabled(True)
            tree.viewport().update()

        move_timer.timeout.connect(apply_unfreeze)
        panel = window._file_system_panel
        panel.path_about_to_move.connect(freeze_tree)
        panel.path_renamed.connect(unfreeze_tree)
        panel.path_deleted.connect(unfreeze_tree)
        panel.path_created.connect(unfreeze_tree)
        return move_timer
