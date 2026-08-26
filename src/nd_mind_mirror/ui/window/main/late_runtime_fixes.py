"""Apply focused runtime fixes without creating backup or duplicate project files."""

from __future__ import annotations

import base64
import ctypes
import gc
import json
import re
import struct
from pathlib import Path
from types import MethodType
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QProcess, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer
from nd_mind_mirror.graphic.core.document_manager import GraphicDocumentManager
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.window.main.main_window import MainWindow


class _DeleteDialogFocusFilter(QObject):
    """Make destructive confirmation keyboard-friendly without changing its workflow."""

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


class _PreviewWheelScrollFilter(QObject):
    """Scroll the PDF viewport directly so search/highlight can never swallow wheel input."""

    def __init__(self, pdf_view, parent=None) -> None:
        super().__init__(parent)
        self._pdf_view = pdf_view

    def eventFilter(self, watched, event) -> bool:
        if watched is not self._pdf_view or event.type() != QEvent.Type.Wheel:
            return super().eventFilter(watched, event)
        if bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            return super().eventFilter(watched, event)

        root = self._pdf_view.rootObject()
        if root is None:
            return super().eventFilter(watched, event)

        pixel = event.pixelDelta()
        angle = event.angleDelta()
        if not pixel.isNull():
            dx = float(-pixel.x())
            dy = float(-pixel.y())
        else:
            dx = float(-angle.x()) * 0.75
            dy = float(-angle.y()) * 0.75

        if bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and dx == 0.0:
            dx, dy = dy, 0.0

        if dx == 0.0 and dy == 0.0:
            return super().eventFilter(watched, event)

        try:
            root.panBy(dx, dy)
        except (AttributeError, RuntimeError, TypeError):
            return super().eventFilter(watched, event)
        event.accept()
        return True


class _IdleMemoryCompactor(QObject):
    """Return unused Python/glibc heap pages periodically while leaving features enabled."""

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
    """Install current editor, Preview, iPad-safety, pinned-tab, and resource fixes."""

    _class_patches_installed = False
    _original_visual_insert_from_mime: Callable | None = None
    _original_activate_bookmark: Callable | None = None
    _original_compile_pending_source: Callable | None = None
    _original_preview_target_for_cursor: Callable | None = None
    _original_find_graphic_reference: Callable | None = None

    @classmethod
    def install_class_patches(cls) -> None:
        if cls._class_patches_installed:
            return
        cls._install_visual_clipboard_image_paste()
        cls._install_bookmark_navigation_retry()
        cls._install_responsive_live_preview()
        cls._install_contextual_preview_target()
        cls._install_existing_png_sidecar_seed()
        cls._class_patches_installed = True

    @classmethod
    def _install_visual_clipboard_image_paste(cls) -> None:
        """Route image paste from Visual through LatexEditor's managed-image insertion."""
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
            owner._go_to_source_location(max(int(line), 1), max(int(column), 1), align_top=False)
            LatexEditor.insertFromMimeData(owner, source)
            owner._visual_dirty = True
            owner._refresh_visual_projection()
            try:
                editor.go_to_source_location(max(int(line), 1), max(int(column), 1), align_top=False)
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
                    QTimer.singleShot(attempts[next_index], lambda attempt=next_index: try_go(attempt))

            QTimer.singleShot(0, try_go)

        MainWindow._activate_bookmark = activate_bookmark

    @classmethod
    def _install_responsive_live_preview(cls) -> None:
        """Interrupt an obsolete compile after the typing debounce and render only the newest generation."""
        original = LatexRenderer._compile_pending_source
        cls._original_compile_pending_source = original

        def compile_pending_source(renderer: LatexRenderer) -> None:
            if renderer._process.state() != QProcess.ProcessState.NotRunning:
                pending = int(getattr(renderer, "_pending_generation", 0))
                active = int(getattr(renderer, "_active_generation", 0))
                latest = int(getattr(renderer, "_latest_requested_generation", 0))
                if pending > active or latest > active:
                    renderer._stop_running_process()
                else:
                    return
            original(renderer)

        LatexRenderer._compile_pending_source = compile_pending_source

    @classmethod
    def _install_contextual_preview_target(cls) -> None:
        """Use a local phrase around the caret so PDF search never synchronizes on one ambiguous word."""
        original = LatexEditor._preview_target_for_cursor.__func__
        cls._original_preview_target_for_cursor = original
        word_re = re.compile(r"[^\W_]+(?:[’'\u200c-][^\W_]+)*", re.UNICODE)

        def preview_target_for_cursor(editor_cls, cursor: QTextCursor, *, visual: bool) -> str:
            if cursor.hasSelection():
                selected = cursor.selectedText().replace("\u2029", " ").strip()
                if not visual:
                    selected = editor_cls._preview_visible_source_text(selected)
                return editor_cls._normalize_preview_target(selected)[:180]

            raw = cursor.block().text()
            offset = max(0, min(cursor.positionInBlock(), len(raw)))
            matches = list(word_re.finditer(raw))
            if not matches:
                return ""
            current_index = None
            for index, match in enumerate(matches):
                if match.start() <= offset <= match.end():
                    current_index = index
                    break
            if current_index is None:
                current_index = min(
                    range(len(matches)),
                    key=lambda index: min(abs(matches[index].start() - offset), abs(matches[index].end() - offset)),
                )
            start = max(current_index - 2, 0)
            end = min(current_index + 3, len(matches))
            raw_target = raw[matches[start].start():matches[end - 1].end()]
            if not visual:
                raw_target = editor_cls._preview_visible_source_text(raw_target)
            value = editor_cls._normalize_preview_target(raw_target)
            if len(value) < 3:
                return ""
            return value[:180]

        LatexEditor._preview_target_for_cursor = classmethod(preview_target_for_cursor)

    @staticmethod
    def _png_dimensions(data: bytes) -> tuple[int, int] | None:
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        try:
            width, height = struct.unpack(">II", data[16:24])
        except struct.error:
            return None
        if width <= 0 or height <= 0:
            return None
        return int(width), int(height)

    @classmethod
    def _seed_new_legacy_sidecar(cls, sidecar: Path, image_path: Path) -> None:
        """Seed a just-created sidecar from an existing PNG instead of opening that PNG as white."""
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            if str(payload.get("background_image_base64", "")).strip():
                return
            if str(payload.get("drawing_data_base64", "")).strip():
                return
            objects = payload.get("image_objects")
            if isinstance(objects, list) and objects:
                return
            image_data = image_path.read_bytes()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        payload["background_image_base64"] = base64.b64encode(image_data).decode("ascii")
        dimensions = cls._png_dimensions(image_data)
        if dimensions is not None:
            payload["canvas_width"], payload["canvas_height"] = dimensions
        temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(sidecar)
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass

    @classmethod
    def _install_existing_png_sidecar_seed(cls) -> None:
        """When an ordinary existing PNG is first sent to iPad, preserve it as the editable background."""
        original_find = GraphicDocumentManager.find_reference
        cls._original_find_graphic_reference = original_find

        def find_reference(manager, source, source_path, position):
            source_file = Path(source_path).expanduser().resolve()
            before_sidecars = {
                candidate.with_suffix(".ndgraphic")
                for candidate in source_file.parent.glob("*.png")
                if candidate.with_suffix(".ndgraphic").is_file()
            }
            reference = original_find(manager, source, source_path, position)
            if reference is None:
                return None
            if (
                reference.sidecar_path not in before_sidecars
                and reference.sidecar_path.is_file()
                and reference.image_path.is_file()
            ):
                cls._seed_new_legacy_sidecar(reference.sidecar_path, reference.image_path)
            return reference

        GraphicDocumentManager.find_reference = find_reference

    @staticmethod
    def install_application(application: QApplication) -> list[QObject]:
        delete_filter = _DeleteDialogFocusFilter(application)
        application.installEventFilter(delete_filter)
        compactor = _IdleMemoryCompactor(application)
        return [delete_filter, compactor]

    @staticmethod
    def install_window(window) -> list[object]:
        """Apply current window-level behavior after every controller has been constructed."""
        keepalive: list[object] = []

        controller = getattr(window, "_workspace_interaction_controller", None)
        if controller is not None:
            renderer = window._renderer
            preview = window._preview_panel.preview
            pending_highlight = {"text": ""}
            highlight_apply_timer = QTimer(window)
            highlight_apply_timer.setSingleShot(True)
            highlight_apply_timer.setInterval(25)

            def write_preview_highlight(_controller, text: str = "") -> None:
                value = str(text or "").strip()
                pdf = getattr(_controller._preview, "_pdf_view", None)
                root = pdf.rootObject() if pdf is not None else None
                if root is None:
                    return
                try:
                    root.setProperty("editHighlightText", value)
                except RuntimeError:
                    return
                _controller._last_highlight_text = value

            def try_apply_highlight() -> None:
                value = pending_highlight["text"]
                try:
                    preview_current = renderer._preview_is_current_for_sync()
                except (AttributeError, RuntimeError):
                    preview_current = False
                sync_timer = getattr(renderer, "_sync_timer", None)
                sync_process = getattr(renderer, "_sync_process", None)
                sync_busy = bool(sync_timer is not None and sync_timer.isActive())
                if sync_process is not None:
                    try:
                        sync_busy = sync_busy or (sync_process.state() != QProcess.ProcessState.NotRunning)
                    except RuntimeError:
                        pass
                if value and (not preview_current or sync_busy):
                    highlight_apply_timer.start()
                    return
                write_preview_highlight(controller, value)

            def request_preview_highlight(_controller, text: str = "") -> None:
                pending_highlight["text"] = str(text or "").strip()
                highlight_apply_timer.start()

            def sync_preview_highlight(_controller) -> None:
                editor = window._editor_panel.current_editor()
                if editor is None or not hasattr(editor, "active_preview_highlight_text"):
                    value = ""
                else:
                    try:
                        value = str(editor.active_preview_highlight_text() or "")
                    except (AttributeError, RuntimeError):
                        value = ""
                request_preview_highlight(_controller, value)

            controller._set_preview_highlight_text = MethodType(request_preview_highlight, controller)
            controller._sync_preview_highlight = MethodType(sync_preview_highlight, controller)
            controller._highlight_timer.stop()
            controller._highlight_timer.setInterval(55)
            controller._highlight_timer.timeout.connect(controller._sync_preview_highlight)

            def set_edit_highlight(text: str) -> None:
                request_preview_highlight(controller, text)

            preview.set_edit_highlight = set_edit_highlight

            def after_source_mapping(*_args) -> None:
                highlight_apply_timer.start()

            renderer.source_position_mapped.connect(after_source_mapping)
            window._editor_panel.current_document_changed.connect(
                lambda *_args: request_preview_highlight(controller, "")
            )
            highlight_apply_timer.timeout.connect(try_apply_highlight)
            keepalive.extend([highlight_apply_timer, after_source_mapping])

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
        navigator = window._file_system_panel
        navigator.path_about_to_move.connect(freeze_tree)
        navigator.path_renamed.connect(unfreeze_tree)
        navigator.path_deleted.connect(unfreeze_tree)
        navigator.path_created.connect(unfreeze_tree)
        keepalive.append(move_timer)

        delete_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Delete"), window)
        delete_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

        def delete_current_file() -> None:
            current = window._editor_panel.current_path()
            if current is None:
                return
            path = Path(current).expanduser().resolve()
            if path.is_file():
                window._file_system_panel._delete_path(path)

        delete_shortcut.activated.connect(delete_current_file)
        keepalive.append(delete_shortcut)

        edit_search_ignore_action = QAction("Edit search_ignore.yaml", window)

        def edit_search_ignore() -> None:
            path = Path(window._app_settings.search_ignore_file_path).expanduser().resolve()
            if not path.is_file():
                QMessageBox.warning(window, "Search Ignore", f"Search ignore file does not exist:\n{path}")
                return
            window._open_path(str(path), select=True, reveal_in_navigator=True)

        edit_search_ignore_action.triggered.connect(edit_search_ignore)
        for menu_action in window.menuBar().actions():
            if menu_action.text().replace("&", "").strip() != "Settings":
                continue
            settings_menu = menu_action.menu()
            if settings_menu is None:
                break
            reload_action = getattr(window, "_reload_settings_action", None)
            if reload_action is not None:
                settings_menu.insertAction(reload_action, edit_search_ignore_action)
            else:
                settings_menu.addAction(edit_search_ignore_action)
            break
        keepalive.append(edit_search_ignore_action)

        pinned = getattr(window, "_pinned_tab_controller", None)
        if pinned is not None:
            pin_bar = pinned._pin_bar
            pin_bar.setTabsClosable(True)

            def close_pinned(index: int) -> None:
                if index < 0 or index >= len(pinned._pin_bar_paths):
                    return
                path = Path(pinned._pin_bar_paths[index])
                pinned.unpin_path(path)
                target = window._editor_panel._index_for_path(path)
                if target >= 0:
                    window._editor_panel.close_tab(target)

            pin_bar.tabCloseRequested.connect(close_pinned)

        structure_controller = getattr(window, "_structure_highlight_controller", None)
        if structure_controller is not None:
            structure_panel = window._structure_panel
            structure_panel._apply_current_line_highlight = structure_controller.apply_highlight
            structure_controller.apply_highlight()

        preview_panel = window._preview_panel
        preview = preview_panel.preview
        pdf_view = preview._pdf_view
        root = pdf_view.rootObject()

        wheel_scroll_filter = _PreviewWheelScrollFilter(pdf_view, window)
        pdf_view.installEventFilter(wheel_scroll_filter)
        keepalive.append(wheel_scroll_filter)

        graphic_timer = getattr(window, "_graphic_preview_refresh_timer", None)
        if graphic_timer is not None:
            graphic_timer.setInterval(140)

        auto_fit = getattr(window, "_preview_auto_fit_controller", None)
        if auto_fit is not None:
            for timer_name in ("_recenter_timer", "_late_recenter_timer"):
                timer = getattr(auto_fit, timer_name, None)
                if timer is not None:
                    timer.stop()
            if root is not None:
                signal = getattr(root, "reloadTokenChanged", None)
                callback = getattr(auto_fit, "_on_preview_reloaded", None)
                if signal is not None and callback is not None:
                    try:
                        signal.disconnect(callback)
                    except (RuntimeError, TypeError):
                        pass

        lock_button = QPushButton("Lock", preview_panel)
        lock_button.setCheckable(True)
        lock_button.setToolTip(
            "Lock Preview position and zoom against Source/Visual synchronization and live reload jumps"
        )
        preview_panel._controls_layout.insertWidget(2, lock_button)
        preview_panel._latex_controls.insert(2, lock_button)
        preview._nd_view_locked = False
        original_scroll_to_source = preview.scroll_to_source_location

        def locked_scroll_to_source(_preview, page: int, x: float, y: float) -> None:
            if bool(getattr(_preview, "_nd_view_locked", False)):
                return
            original_scroll_to_source(page, x, y)

        preview.scroll_to_source_location = MethodType(locked_scroll_to_source, preview)
        try:
            window._renderer.source_position_mapped.disconnect(original_scroll_to_source)
        except (RuntimeError, TypeError):
            pass
        window._renderer.source_position_mapped.connect(preview.scroll_to_source_location)

        def set_preview_lock(locked: bool) -> None:
            preview._nd_view_locked = bool(locked)
            lock_button.setText("Locked" if locked else "Lock")
            if root is not None:
                try:
                    if locked:
                        root.captureScrollState()
                    else:
                        root.restoreScrollState()
                except (AttributeError, RuntimeError, TypeError):
                    pass

        lock_button.toggled.connect(set_preview_lock)
        keepalive.append(lock_button)

        extend_button = QPushButton("Extend", preview_panel)
        extend_button.setCheckable(True)
        extend_button.setToolTip("Show only Preview across the main window")
        preview_panel._controls_layout.insertWidget(3, extend_button)
        preview_panel._latex_controls.insert(3, extend_button)
        visibility_state = {
            "navigator": window._navigator_splitter.isVisible(),
            "editor": window._editor_panel.isVisible(),
        }

        def set_extended(enabled: bool) -> None:
            if enabled:
                visibility_state["navigator"] = window._navigator_splitter.isVisible()
                visibility_state["editor"] = window._editor_panel.isVisible()
                window._navigator_splitter.hide()
                window._editor_panel.hide()
                extend_button.setText("Restore")
            else:
                if visibility_state["navigator"]:
                    window._navigator_splitter.show()
                if visibility_state["editor"]:
                    window._editor_panel.show()
                extend_button.setText("Extend")

        extend_button.toggled.connect(set_extended)
        keepalive.append(extend_button)

        return keepalive
