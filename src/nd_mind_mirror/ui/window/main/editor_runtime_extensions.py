"""Centralize the remaining runtime extensions for editor performance and selection bookmarks.

The application is class/controller based.  This module is the single compatibility
layer for behaviors that still need to adapt legacy classes at startup; keeping
those adaptations here prevents migration-specific and one-off patch modules from
stacking independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QImage

from nd_mind_mirror.core.bookmark.bookmark_anchor_relocator import BookmarkAnchorRelocator
from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.bookmark.bookmark_gutter import BookmarkGutter
from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel
from nd_mind_mirror.ui.panel.preview.preview_panel import PreviewPanel
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.enhanced_main_window import EnhancedMainWindow
from nd_mind_mirror.ui.window.main.main_window import MainWindow
from nd_mind_mirror.ui.window.main.runtime_fixes import _BookmarkManagerController
from nd_mind_mirror.ui.window.main.visual_persian_font_core import VisualPersianFontController
from nd_mind_mirror.ui.window.main.visual_window_controller import VisualWindowController


def _int_setting(
    settings: YamlSettings,
    section: str,
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(settings._get(section, key, default=default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _float_setting(
    settings: YamlSettings,
    section: str,
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        value = float(settings._get(section, key, default=default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


class EditorRuntimeExtensions:
    """Install the one remaining legacy adaptation layer exactly once."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return
        cls._configure_persian_font_defaults()
        cls._install_source_layout_settings()
        cls._install_visual_window_settings()
        cls._install_preview_render_settings()
        cls._install_bookmark_relocation()
        cls._install_selection_bookmarks()
        cls._installed = True

    @staticmethod
    def _configure_persian_font_defaults() -> None:
        """Use the same Persian fallback order as the shipped settings."""
        VisualPersianFontController.DEFAULT_FONT_FAMILY = "Noto Sans Arabic"
        VisualPersianFontController._FALLBACK_FAMILIES = (
            "Noto Sans Arabic",
            "Noto Naskh Arabic",
            "Vazirmatn",
            "DejaVu Sans",
        )

    @staticmethod
    def _install_source_layout_settings() -> None:
        """Apply one configurable debounce to incremental source relayout."""
        for editor_class in (LatexEditor, GenericTextEditor, YamlEditor):
            original_apply: Callable = editor_class.apply_settings

            def apply_settings(editor, app_settings, _original=original_apply) -> None:
                _original(editor, app_settings)
                timer = getattr(editor, "_block_layout_timer", None)
                if timer is not None:
                    timer.setInterval(
                        _int_setting(
                            app_settings,
                            "editor",
                            "source_layout_update_debounce_ms",
                            40,
                            0,
                            1000,
                        )
                    )

            editor_class.apply_settings = apply_settings

    @staticmethod
    def _apply_visual_window_settings(
        controller: VisualWindowController,
        settings: YamlSettings,
    ) -> None:
        """Keep Visual projection bounded around the active source location."""
        controller_type = type(controller)
        controller_type._PAGES_ABOVE = _int_setting(
            settings, "editor", "visual_window_pages_above", 4, 0, 100
        )
        controller_type._PAGES_BELOW = _int_setting(
            settings, "editor", "visual_window_pages_below", 4, 0, 100
        )
        controller_type._ESTIMATED_CHARS_PER_PAGE = _int_setting(
            settings,
            "editor",
            "visual_window_estimated_chars_per_page",
            2400,
            200,
            20000,
        )
        controller_type._MIN_LINES_PER_PAGE = _int_setting(
            settings, "editor", "visual_window_min_lines_per_page", 12, 1, 500
        )
        controller_type._MAX_LINES_PER_PAGE = max(
            controller_type._MIN_LINES_PER_PAGE,
            _int_setting(
                settings,
                "editor",
                "visual_window_max_lines_per_page",
                45,
                1,
                2000,
            ),
        )
        controller_type._SCROLL_REWINDOW_DELAY_MS = _int_setting(
            settings,
            "editor",
            "visual_window_rewindow_delay_ms",
            90,
            10,
            2000,
        )
        controller_type._SCROLL_EDGE_RATIO = _float_setting(
            settings,
            "editor",
            "visual_window_scroll_edge_ratio",
            0.14,
            0.02,
            0.45,
        )
        # The previous bounded subclass existed only to lower these thresholds.
        # Keep the behavior on the canonical controller and remove that duplicate.
        controller_type._MIN_VIRTUAL_SOURCE_CHARS = 24_000
        controller_type._MIN_VIRTUAL_BODY_LINES = 220

        for state in getattr(controller, "_states", {}).values():
            timer = state.get("scroll_timer") if isinstance(state, dict) else None
            if timer is not None:
                timer.setInterval(controller_type._SCROLL_REWINDOW_DELAY_MS)

    @classmethod
    def _install_visual_window_settings(cls) -> None:
        """Apply Visual settings at construction and after Settings reload."""
        original_init: Callable = VisualWindowController.__init__

        def init(controller, editor_panel, parent=None) -> None:
            settings = getattr(editor_panel, "_app_settings", None)
            if isinstance(settings, YamlSettings):
                cls._apply_visual_window_settings(controller, settings)
            original_init(controller, editor_panel, parent)
            if isinstance(settings, YamlSettings):
                cls._apply_visual_window_settings(controller, settings)

        def reload(controller, settings=None) -> None:
            app_settings = settings or getattr(
                controller._editor_panel, "_app_settings", None
            )
            if isinstance(app_settings, YamlSettings):
                cls._apply_visual_window_settings(controller, app_settings)

        VisualWindowController.__init__ = init
        VisualWindowController.reload = reload

        original_reload: Callable = EnhancedMainWindow._reload_yaml_settings

        def reload_window(window) -> bool:
            reloaded = bool(original_reload(window))
            controller = getattr(window, "_visual_window_controller", None)
            if reloaded and controller is not None:
                controller.reload(window._app_settings)
            return reloaded

        EnhancedMainWindow._reload_yaml_settings = reload_window

    @classmethod
    def _configure_pdf_view(
        cls,
        pdf_view: SelectablePdfView,
        settings: YamlSettings,
    ) -> None:
        """Apply bounded PDF zoom and a cheaper manual-Fit raster scan."""
        minimum_percent = _int_setting(
            settings, "preview", "min_zoom_percent", 20, 5, 100
        )
        maximum_percent = _int_setting(
            settings,
            "preview",
            "max_zoom_percent",
            500,
            minimum_percent,
            1200,
        )
        pdf_view._MIN_ZOOM = minimum_percent / 100.0
        pdf_view._MAX_ZOOM = maximum_percent / 100.0
        pdf_view._nd_fit_raster_width_px = _int_setting(
            settings, "preview", "fit_raster_width_px", 480, 160, 2400
        )
        pdf_view._nd_fit_raster_sample_step_px = _int_setting(
            settings, "preview", "fit_raster_sample_step_px", 4, 1, 16
        )
        pdf_view._rendered_bounds_cache.clear()
        root = pdf_view.rootObject()
        if root is None:
            return
        root.setProperty("minSafeZoomScale", float(pdf_view._MIN_ZOOM))
        root.setProperty("maxSafeZoomScale", float(pdf_view._MAX_ZOOM))
        try:
            current = float(root.property("zoomScale"))
        except (TypeError, ValueError):
            current = 1.0
        root.setProperty(
            "zoomScale",
            max(pdf_view._MIN_ZOOM, min(current, pdf_view._MAX_ZOOM)),
        )

    @classmethod
    def _install_preview_render_settings(cls) -> None:
        """Use settings-driven limits without allocating large Fit textures."""

        def rendered_bounds(
            pdf_view,
            page_index: int,
            page_width_points: float,
            page_height_points: float,
        ):
            if page_width_points <= 0 or page_height_points <= 0:
                return None
            cache_key = (str(pdf_view._fit_document_path or ""), int(page_index))
            if cache_key in pdf_view._rendered_bounds_cache:
                return pdf_view._rendered_bounds_cache[cache_key]
            try:
                width = max(
                    int(getattr(pdf_view, "_nd_fit_raster_width_px", 480)), 1
                )
                step = max(
                    int(getattr(pdf_view, "_nd_fit_raster_sample_step_px", 4)), 1
                )
                height = max(
                    1,
                    int(round(width * page_height_points / page_width_points)),
                )
                image = pdf_view._fit_document.render(
                    int(page_index), QSize(width, height)
                )
                if image.isNull():
                    return None
                image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                width, height = image.width(), image.height()
                data = bytes(image.constBits())
                stride = image.bytesPerLine()
                min_x, max_x = width, -1
                for y in range(0, height, step):
                    row = y * stride
                    for x in range(0, width, step):
                        offset = row + x * 4
                        red, green, blue, alpha = data[offset : offset + 4]
                        if alpha >= 8 and (
                            red < 248 or green < 248 or blue < 248
                        ):
                            min_x = min(min_x, x)
                            max_x = max(max_x, x)
                if max_x < min_x:
                    pdf_view._rendered_bounds_cache[cache_key] = None
                    return None
                scale = page_width_points / float(width)
                result = (
                    min_x * scale,
                    min((max_x + step) * scale, page_width_points),
                )
                pdf_view._rendered_bounds_cache[cache_key] = result
                return result
            except Exception:
                pdf_view._rendered_bounds_cache[cache_key] = None
                return None

        SelectablePdfView._rendered_ink_x_bounds_points = rendered_bounds

        def set_default_zoom_percent(preview, percent: int | float) -> None:
            minimum = float(preview._pdf_view._MIN_ZOOM) * 100.0
            maximum = float(preview._pdf_view._MAX_ZOOM) * 100.0
            preview._default_zoom_percent = max(
                minimum, min(float(percent), maximum)
            )
            if preview._current_pdf_path is not None and not preview._fit_active:
                preview._pdf_view.set_zoom_percent(preview._default_zoom_percent)

        LatexPreview.set_default_zoom_percent = set_default_zoom_percent

        original_panel_apply: Callable = PreviewPanel.apply_settings

        def panel_apply(panel, *args, **kwargs) -> None:
            original_panel_apply(panel, *args, **kwargs)
            settings = getattr(panel.window(), "_app_settings", None)
            if not isinstance(settings, YamlSettings):
                return
            cls._configure_pdf_view(panel._preview._pdf_view, settings)
            panel._nd_min_zoom_percent = int(
                round(panel._preview._pdf_view._MIN_ZOOM * 100)
            )
            panel._nd_max_zoom_percent = int(
                round(panel._preview._pdf_view._MAX_ZOOM * 100)
            )
            panel._zoom_edit.setToolTip(
                "PDF zoom percentage "
                f"({panel._nd_min_zoom_percent}% to {panel._nd_max_zoom_percent}%)"
            )

        PreviewPanel.apply_settings = panel_apply

        def apply_zoom_edit(panel) -> None:
            raw = panel._zoom_edit.text().strip().rstrip("%").strip()
            try:
                percent = int(round(float(raw)))
            except ValueError:
                percent = int(round(float(panel._preview._default_zoom_percent)))
            minimum = int(getattr(panel, "_nd_min_zoom_percent", 20))
            maximum = int(getattr(panel, "_nd_max_zoom_percent", 500))
            percent = max(minimum, min(percent, maximum))
            panel._zoom_edit.setText(f"{percent}%")
            panel._preview.set_zoom_percent(percent)

        PreviewPanel._apply_zoom_edit = apply_zoom_edit

    @staticmethod
    def _install_bookmark_relocation() -> None:
        """Relocate saved selection endpoints together with their bookmark."""

        def relocate(relocator, bookmarks, source):
            lines = str(source).splitlines() or [""]
            normalized = [relocator.normalize_line(line) for line in lines]
            output: list[dict[str, object]] = []
            changed = False

            for raw in bookmarks:
                item = dict(raw)
                try:
                    old_line = max(int(raw.get("line", 1)), 1)
                except (TypeError, ValueError):
                    old_line = 1
                old_line = min(old_line, len(lines))
                try:
                    column = max(int(raw.get("column", 1)), 1)
                except (TypeError, ValueError):
                    column = 1

                anchor = relocator.normalize_line(str(raw.get("anchor", "")))
                current_anchor = normalized[old_line - 1]
                new_line = old_line
                if anchor and current_anchor != anchor:
                    candidates = [
                        index + 1
                        for index, value in enumerate(normalized)
                        if value == anchor
                    ]
                    if candidates:
                        new_line = min(
                            candidates,
                            key=lambda value: abs(value - old_line),
                        )
                    else:
                        anchor = current_anchor
                elif not anchor:
                    anchor = current_anchor

                delta = new_line - old_line
                item.update(
                    line=new_line,
                    column=min(column, len(lines[new_line - 1]) + 1),
                    name=str(raw.get("name", "")).strip(),
                    anchor=anchor,
                )
                for prefix in ("selection_anchor", "selection_position"):
                    line_key = f"{prefix}_line"
                    column_key = f"{prefix}_column"
                    if line_key not in item:
                        continue
                    try:
                        selected_line = max(
                            1,
                            min(int(item[line_key]) + delta, len(lines)),
                        )
                        selected_column = max(int(item.get(column_key, 1)), 1)
                    except (TypeError, ValueError):
                        continue
                    item[line_key] = selected_line
                    item[column_key] = min(
                        selected_column,
                        len(lines[selected_line - 1]) + 1,
                    )
                output.append(item)
                changed = changed or (
                    new_line != old_line
                    or anchor
                    != relocator.normalize_line(str(raw.get("anchor", "")))
                )

            output.sort(
                key=lambda item: (
                    int(item.get("line", 1)),
                    int(item.get("column", 1)),
                )
            )
            return output, changed

        BookmarkAnchorRelocator.relocate = relocate

    @staticmethod
    def _label_text(value: str, limit: int = 240) -> str:
        return " ".join(
            str(value or "").replace("\u2029", "\n").split()
        )[:limit]

    @classmethod
    def _selection_payload(cls, editor: LatexEditor) -> dict[str, object]:
        """Capture a Source or Visual selection in canonical source coordinates."""
        if getattr(editor, "_edit_mode", "source") == "visual":
            cursor = editor._visual_editor.textCursor()
            if not cursor.hasSelection():
                return {}
            anchor, position = editor._visual_editor.source_selection_locations()
            visible = cursor.selectedText().replace("\u2029", "\n")
        else:
            cursor = editor.textCursor()
            if not cursor.hasSelection():
                return {}
            anchor = editor._source_location_for_position(cursor.anchor())
            position = editor._source_location_for_position(cursor.position())
            visible = cursor.selectedText().replace("\u2029", "\n")

        if anchor == position:
            return {}
        first = editor._source_position_for_location(anchor)
        second = editor._source_position_for_location(position)
        source_text = editor.toPlainText()[min(first, second) : max(first, second)]
        try:
            preview_text = str(editor.active_preview_highlight_text() or "")
        except (AttributeError, RuntimeError):
            preview_text = visible
        return {
            "selection_anchor_line": int(anchor[0]),
            "selection_anchor_column": int(anchor[1]),
            "selection_position_line": int(position[0]),
            "selection_position_column": int(position[1]),
            "selection_text": cls._label_text(preview_text or visible),
            "selection_source_text": source_text[:8000],
        }

    @staticmethod
    def _has_selection(bookmark: dict[str, object]) -> bool:
        return all(
            key in bookmark
            for key in (
                "selection_anchor_line",
                "selection_anchor_column",
                "selection_position_line",
                "selection_position_column",
            )
        )

    @classmethod
    def _activate_payload(
        cls,
        window: MainWindow,
        path: str,
        bookmark: dict[str, object],
    ) -> None:
        """Open a bookmark target, then restore it once its editor is active."""
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file():
            window._show_warning(f"Bookmarked file does not exist: {file_path}")
            return
        window._open_path(str(file_path), select=True, reveal_in_navigator=True)
        payload = dict(bookmark)
        attempts = (0, 20, 50, 100, 180, 300)

        def try_activate(index: int = 0) -> None:
            current = window._editor_panel.current_path()
            current_path = None
            if current is not None:
                try:
                    current_path = Path(current).expanduser().resolve()
                except OSError:
                    current_path = None
            if current_path == file_path:
                window._editor_panel.activate_bookmark(payload)
                return
            next_index = index + 1
            if next_index < len(attempts):
                QTimer.singleShot(
                    attempts[next_index],
                    lambda value=next_index: try_activate(value),
                )

        QTimer.singleShot(0, try_activate)

    @classmethod
    def _install_selection_bookmarks(cls) -> None:
        """Store and restore exact selection ranges without patching MainWindow navigation."""
        original_editor_init: Callable = LatexEditor.__init__

        def editor_init(editor, *args, **kwargs) -> None:
            original_editor_init(editor, *args, **kwargs)
            for gutter in (
                editor._source_bookmark_gutter,
                editor._visual_bookmark_gutter,
            ):
                gutter._nd_bookmark_activate_callback = (
                    lambda bookmark, item=editor: item.activate_bookmark(bookmark)
                )
                gutter.setToolTip(
                    "Click a bookmark to restore its selection; click an empty "
                    "line to add one. Right-click to rename/remove."
                )

        LatexEditor.__init__ = editor_init

        original_mouse: Callable = BookmarkGutter.mousePressEvent

        def gutter_mouse(gutter, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                existing = gutter._bookmark_near_y(int(event.position().y()))
                callback = getattr(
                    gutter, "_nd_bookmark_activate_callback", None
                )
                if existing is not None and callable(callback):
                    callback(dict(existing))
                    event.accept()
                    return
            original_mouse(gutter, event)

        BookmarkGutter.mousePressEvent = gutter_mouse

        def set_bookmarks(editor, bookmarks) -> None:
            source_lines = editor.toPlainText().splitlines() or [""]
            normalized: list[dict[str, object]] = []
            for raw in bookmarks or []:
                if not isinstance(raw, dict):
                    continue
                item = dict(raw)
                try:
                    line = max(
                        1,
                        min(int(raw.get("line", 1)), len(source_lines)),
                    )
                    column = max(
                        1,
                        min(
                            int(raw.get("column", 1)),
                            len(source_lines[line - 1]) + 1,
                        ),
                    )
                except (TypeError, ValueError):
                    line, column = 1, 1
                item.update(
                    line=line,
                    column=column,
                    name=str(raw.get("name", "")).strip(),
                    anchor=editor._bookmark_relocator.normalize_line(
                        str(raw.get("anchor", "")) or source_lines[line - 1]
                    ),
                )
                if "selection_text" in item:
                    item["selection_text"] = cls._label_text(
                        str(item.get("selection_text", ""))
                    )
                normalized.append(item)
            editor._bookmarks, _changed = editor._bookmark_relocator.relocate(
                normalized, editor.toPlainText()
            )
            editor._update_bookmark_gutters()

        LatexEditor.set_bookmarks = set_bookmarks

        def toggle_bookmark(editor, line: int, column: int) -> None:
            existing = editor._bookmark_for_location(line, column)
            if existing is not None:
                editor._bookmarks.remove(existing)
            else:
                lines = editor.toPlainText().splitlines() or [""]
                line = max(1, min(int(line), len(lines)))
                column = max(1, int(column))
                payload = cls._selection_payload(editor)
                if payload:
                    first = editor._source_position_for_location(
                        (
                            int(payload["selection_anchor_line"]),
                            int(payload["selection_anchor_column"]),
                        )
                    )
                    second = editor._source_position_for_location(
                        (
                            int(payload["selection_position_line"]),
                            int(payload["selection_position_column"]),
                        )
                    )
                    clicked = editor._source_position_for_location((line, column))
                    if not min(first, second) <= clicked <= max(first, second):
                        payload = {}
                if payload:
                    endpoints = [
                        (
                            int(payload["selection_anchor_line"]),
                            int(payload["selection_anchor_column"]),
                        ),
                        (
                            int(payload["selection_position_line"]),
                            int(payload["selection_position_column"]),
                        ),
                    ]
                    line, column = min(
                        endpoints,
                        key=lambda value: editor._source_position_for_location(value),
                    )
                item: dict[str, object] = {
                    "line": int(line),
                    "column": int(column),
                    "name": "",
                    "anchor": editor._bookmark_relocator.normalize_line(
                        lines[int(line) - 1]
                    ),
                }
                item.update(payload)
                editor._bookmarks.append(item)
                editor._bookmarks.sort(
                    key=lambda value: (
                        int(value.get("line", 1)),
                        int(value.get("column", 1)),
                    )
                )
            editor._emit_bookmarks_changed()

        LatexEditor._toggle_bookmark = toggle_bookmark

        def activate_bookmark(editor, bookmark) -> None:
            if not isinstance(bookmark, dict):
                return
            try:
                line = max(int(bookmark.get("line", 1)), 1)
                column = max(int(bookmark.get("column", 1)), 1)
            except (TypeError, ValueError):
                line, column = 1, 1
            if not cls._has_selection(bookmark):
                editor.go_to_source_location(line, column, align_top=True)
                return
            try:
                anchor = (
                    max(int(bookmark["selection_anchor_line"]), 1),
                    max(int(bookmark["selection_anchor_column"]), 1),
                )
                position = (
                    max(int(bookmark["selection_position_line"]), 1),
                    max(int(bookmark["selection_position_column"]), 1),
                )
            except (TypeError, ValueError, KeyError):
                editor.go_to_source_location(line, column, align_top=True)
                return

            preview_text = str(
                bookmark.get("selection_text")
                or bookmark.get("selection_source_text")
                or ""
            )
            editor._nd_shared_selection = (anchor, position, preview_text)
            editor._refresh_visual_projection()
            editor._syncing_cursor_views = True
            try:
                editor._set_source_selection_from_locations(anchor, position)
                editor._visual_editor.set_selection_from_source_locations(
                    anchor,
                    position,
                    ensure_visible=(
                        getattr(editor, "_edit_mode", "source") == "visual"
                    ),
                )
            finally:
                editor._syncing_cursor_views = False
            active = (
                editor._visual_editor
                if getattr(editor, "_edit_mode", "source") == "visual"
                else editor
            )
            active.ensureCursorVisible()
            active.setFocus()
            editor.active_cursor_changed.emit()
            editor.active_view_changed.emit()

        LatexEditor.activate_bookmark = activate_bookmark

        def panel_activate(panel, bookmark) -> None:
            editor = panel.current_editor()
            if isinstance(editor, LatexEditor):
                editor.activate_bookmark(bookmark)

        EditorPanel.activate_bookmark = panel_activate

        def refresh_menu(window) -> None:
            if not hasattr(window, "_bookmarks_menu"):
                return
            menu = window._bookmarks_menu
            menu.clear()
            menu.addAction(window._toggle_bookmark_action)
            entries = []
            for raw_path, bookmarks in window._editor_panel.bookmarks().items():
                for bookmark in bookmarks:
                    try:
                        line = max(int(bookmark.get("line", 1)), 1)
                        column = max(int(bookmark.get("column", 1)), 1)
                    except (TypeError, ValueError):
                        continue
                    name = str(bookmark.get("name", "")).strip()
                    selection = cls._label_text(
                        str(bookmark.get("selection_text", ""))
                    )
                    anchor = str(bookmark.get("anchor", "")).strip()
                    label = name or selection or anchor[:48] or f"Line {line}"
                    entries.append(
                        (
                            str(raw_path),
                            line,
                            column,
                            label,
                            Path(str(raw_path)).name,
                            dict(bookmark),
                        )
                    )
            if entries:
                menu.addSeparator()
                for (
                    raw_path,
                    line,
                    column,
                    label,
                    filename,
                    bookmark,
                ) in sorted(
                    entries,
                    key=lambda item: (item[0].casefold(), item[1], item[2]),
                ):
                    action = menu.addAction(
                        f"{label} - {filename}:{line}:{column}"
                    )
                    action.setToolTip(raw_path)
                    action.triggered.connect(
                        lambda _checked=False,
                        path=raw_path,
                        payload=dict(bookmark): cls._activate_payload(
                            window, path, payload
                        )
                    )
            else:
                empty = menu.addAction("No bookmarks")
                empty.setEnabled(False)

            controller = getattr(window, "_nd_bookmark_manager", None)
            if controller is not None:
                menu.addSeparator()
                action = menu.addAction("Manage Bookmarks...")
                action.triggered.connect(controller.show)
                window._nd_manage_bookmarks_action = action

        MainWindow._refresh_bookmarks_menu = refresh_menu

        def manager_entries(controller):
            result = []
            for raw_path, bookmarks in controller._window._editor_panel.bookmarks().items():
                for bookmark in bookmarks:
                    try:
                        line = max(int(bookmark.get("line", 1)), 1)
                        column = max(int(bookmark.get("column", 1)), 1)
                    except (TypeError, ValueError):
                        continue
                    name = str(bookmark.get("name", "")).strip()
                    selection = cls._label_text(
                        str(bookmark.get("selection_text", ""))
                    )
                    anchor = str(bookmark.get("anchor", "")).strip()
                    result.append(
                        {
                            "path": str(raw_path),
                            "filename": Path(str(raw_path)).name,
                            "line": line,
                            "column": column,
                            "label": (
                                name
                                or selection
                                or anchor[:60]
                                or f"Line {line}"
                            ),
                            "bookmark": dict(bookmark),
                        }
                    )
            result.sort(
                key=lambda item: (
                    str(item["path"]).casefold(),
                    int(item["line"]),
                    int(item["column"]),
                )
            )
            return result

        def manager_activate(controller, entry) -> None:
            bookmark = entry.get("bookmark")
            if isinstance(bookmark, dict):
                cls._activate_payload(
                    controller._window,
                    str(entry["path"]),
                    dict(bookmark),
                )
            else:
                controller._window._activate_bookmark(
                    str(entry["path"]),
                    int(entry["line"]),
                    int(entry["column"]),
                )

        _BookmarkManagerController.entries = manager_entries
        _BookmarkManagerController.activate = manager_activate
