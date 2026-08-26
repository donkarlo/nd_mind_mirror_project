"""Persian typography, bookmark/caret overlays, and three-way selection sync."""
from __future__ import annotations

from pathlib import Path
import unicodedata
import weakref

import yaml

from PySide6.QtCore import QEvent, QObject, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QPalette,
    QPen,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtQuick import QQuickItem
from PySide6.QtWidgets import QApplication, QWidget

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.highlighter.latex.latex_syntax_highlighter import (
    LatexSyntaxHighlighter,
)
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview
from nd_mind_mirror.ui.window.main.persistent_caret_overlay import (
    PersistentCaretOverlay,
)
from nd_mind_mirror.ui.window.main.workspace_interaction_controller import (
    WorkspaceInteractionController,
)


def _is_arabic_script_character(character: str) -> bool:
    if not character:
        return False
    codepoint = ord(character)
    return (
        0x0600 <= codepoint <= 0x08FF
        or 0xFB50 <= codepoint <= 0xFDFF
        or 0xFE70 <= codepoint <= 0xFEFF
        or codepoint in {0x200C, 0x200D}
    )


def _persian_runs(text: str):
    """Yield Arabic/Persian runs while keeping combining marks with the base glyph."""
    start: int | None = None
    for index, character in enumerate(text):
        belongs = _is_arabic_script_character(character)
        if start is not None and unicodedata.combining(character):
            belongs = True
        if belongs and start is None:
            start = index
        elif not belongs and start is not None:
            yield start, index - start
            start = None
    if start is not None:
        yield start, len(text) - start


def _set_family(character_format: QTextCharFormat, family: str) -> None:
    try:
        character_format.setFontFamilies([family])
    except AttributeError:
        character_format.setFontFamily(family)


class PersianVisualFontHighlighter(QSyntaxHighlighter):
    """Force one shaping-capable font for Persian runs in Visual mode."""

    def __init__(self, document, font_family: str) -> None:
        super().__init__(document)
        self._font_family = str(font_family).strip()

    def set_font_family(self, value: str) -> None:
        value = str(value).strip()
        if value == self._font_family:
            return
        self._font_family = value
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not self._font_family:
            return
        for start, length in _persian_runs(text):
            character_format = QTextCharFormat()
            _set_family(character_format, self._font_family)
            self.setFormat(start, length, character_format)


class VisualPersianFontController:
    """Keep the same Persian shaping font in Source and Visual."""

    DEFAULT_FONT_FAMILY = "Noto Naskh Arabic"
    _FALLBACK_FAMILIES = (
        "Noto Naskh Arabic",
        "Noto Sans Arabic",
        "Vazirmatn",
        "DejaVu Sans",
    )

    def __init__(self, editor_panel, app_settings, parent=None) -> None:
        self._editor_panel = editor_panel
        self._app_settings = app_settings
        self._parent = parent
        self._font_family = self.DEFAULT_FONT_FAMILY
        self._highlighters: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
        editor_panel.current_document_changed.connect(self._on_editor_changed)
        editor_panel.current_view_changed.connect(self._on_editor_changed)
        self.reload()

    def reload(self) -> None:
        requested = self._read_persian_font_family(self._app_settings.settings_path)
        self._font_family = self._resolve_installed_family(requested)
        self._bind_current_editor()

    def _on_editor_changed(self, *_args) -> None:
        self._bind_current_editor()

    def _bind_current_editor(self) -> None:
        editor = self._editor_panel.current_editor()
        if isinstance(editor, LatexEditor):
            self._bind_editor(editor)
            _apply_editor_preferences(editor, self._app_settings)

    def _bind_editor(self, editor: LatexEditor) -> None:
        visual = editor._visual_editor
        highlighter = self._highlighters.get(visual)
        if highlighter is None:
            highlighter = PersianVisualFontHighlighter(
                visual.document(), self._font_family
            )
            self._highlighters[visual] = highlighter
        else:
            highlighter.set_font_family(self._font_family)

        source_highlighter = getattr(editor, "_highlighter", None)
        if source_highlighter is not None:
            source_highlighter._nd_persian_font_family = self._font_family
            try:
                source_highlighter.rehighlight()
            except RuntimeError:
                pass

    @classmethod
    def _resolve_installed_family(cls, requested: str) -> str:
        try:
            available = {
                str(family).casefold(): str(family)
                for family in QFontDatabase.families()
            }
        except Exception:
            return requested or cls.DEFAULT_FONT_FAMILY
        for candidate in (requested, *cls._FALLBACK_FAMILIES):
            value = str(candidate or "").strip()
            if not value:
                continue
            resolved = available.get(value.casefold())
            if resolved:
                return resolved
        return requested or cls.DEFAULT_FONT_FAMILY

    @classmethod
    def _read_persian_font_family(cls, settings_path: str | Path) -> str:
        try:
            data = yaml.safe_load(Path(settings_path).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return cls.DEFAULT_FONT_FAMILY
        editor = data.get("editor", {}) if isinstance(data, dict) else {}
        if not isinstance(editor, dict):
            return cls.DEFAULT_FONT_FAMILY
        return str(
            editor.get("persian_font_family")
            or editor.get("visual_persian_font_family")
            or cls.DEFAULT_FONT_FAMILY
        ).strip()


class _BookmarkUnderlineOverlay(QWidget):
    """Draw a faint blue underline at visible bookmark locations."""

    def __init__(self, editor, marker_y_for_location, bookmarks_provider) -> None:
        super().__init__(editor.viewport())
        self._editor = editor
        self._marker_y_for_location = marker_y_for_location
        self._bookmarks_provider = bookmarks_provider
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        editor.viewport().installEventFilter(self)
        editor.verticalScrollBar().valueChanged.connect(self.refresh)
        editor.horizontalScrollBar().valueChanged.connect(self.refresh)
        self._sync_geometry()
        self.show()
        self.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._editor.viewport() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        }:
            self._sync_geometry()
            self.raise_()
            self.update()
        return False

    def _sync_geometry(self) -> None:
        self.setGeometry(self._editor.viewport().rect())

    def refresh(self, *_args) -> None:
        self.update()

    def paintEvent(self, event) -> None:
        del event
        if not self._editor.isVisible():
            return
        color = QColor("#64b5f6")
        color.setAlpha(145)
        pen = QPen(color)
        pen.setWidthF(1.25)
        painter = QPainter(self)
        painter.setPen(pen)
        line_height = max(self._editor.fontMetrics().height(), 4)
        for bookmark in self._bookmarks_provider():
            try:
                y = self._marker_y_for_location(
                    int(bookmark.get("line", 0)),
                    int(bookmark.get("column", 1)),
                )
            except Exception:
                y = None
            if y is None:
                continue
            underline_y = int(round(float(y) + line_height * 0.42))
            if -2 <= underline_y <= self.height() + 2:
                painter.drawLine(
                    22,
                    underline_y,
                    max(self.width() - 8, 26),
                    underline_y,
                )
        painter.end()


class _PreviewCaretOverlay(QWidget):
    """Draw a bold purple SyncTeX caret in Preview when no text is selected."""

    _REFRESH_MS = 250

    def __init__(self, preview: LatexPreview) -> None:
        super().__init__(preview._pdf_view)
        self._preview = preview
        self._page = -1
        self._x = 0.0
        self._y = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._sync_geometry()
        self.show()
        self.raise_()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._timer.setInterval(self._REFRESH_MS)
        self._timer.timeout.connect(self._refresh_if_visible)
        self._timer.start()

    def set_target(self, page: int, x: float, y: float) -> None:
        self._page = max(int(page), 0)
        self._x = float(x)
        self._y = float(y)
        self.raise_()
        self.update()

    def _sync_geometry(self) -> None:
        view = self._preview._pdf_view
        if self.geometry() != view.rect():
            self.setGeometry(view.rect())

    def _refresh_if_visible(self) -> None:
        if self._preview.isVisible() and self._page >= 0:
            self._sync_geometry()
            self.raise_()
            self.update()

    def paintEvent(self, event) -> None:
        del event
        view = self._preview._pdf_view
        if (
            self._page < 0
            or not self._preview.isVisible()
            or bool(getattr(view, "_nd_selection_highlight_active", False))
        ):
            return
        root = view.rootObject()
        if not isinstance(root, QQuickItem):
            return
        paper = self._find_page_paper(root, self._page)
        if paper is None:
            return
        try:
            page_scale = float(paper.property("pageScale"))
        except (TypeError, ValueError):
            return
        if page_scale <= 0:
            return
        try:
            marker_rect = paper.mapRectToItem(
                root,
                QRectF(
                    self._x * page_scale - 1.0,
                    self._y * page_scale - 9.0,
                    2.0,
                    18.0,
                ),
            )
        except (AttributeError, RuntimeError, TypeError):
            return
        pen = QPen(QColor("#7b2cbf"))
        pen.setWidthF(3.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter = QPainter(self)
        painter.setPen(pen)
        painter.drawLine(
            marker_rect.center().x(),
            marker_rect.top(),
            marker_rect.center().x(),
            marker_rect.bottom(),
        )
        painter.end()

    @classmethod
    def _find_page_paper(cls, item: QQuickItem, page: int):
        try:
            meta = item.metaObject()
            if (
                meta.indexOfProperty("pageScale") >= 0
                and meta.indexOfProperty("pagePointSize") >= 0
            ):
                parent = item.parentItem()
                while parent is not None:
                    parent_meta = parent.metaObject()
                    if parent_meta.indexOfProperty("index") >= 0:
                        try:
                            return item if int(parent.property("index")) == int(page) else None
                        except (TypeError, ValueError):
                            return None
                    parent = parent.parentItem()
        except (AttributeError, RuntimeError):
            pass
        try:
            children = item.childItems()
        except (AttributeError, RuntimeError):
            return None
        for child in children:
            found = cls._find_page_paper(child, page)
            if found is not None:
                return found
        return None


class _PreviewSelectionEventFilter(QObject):
    """Read Qt Quick PDF selection only after user input; no polling."""

    def __init__(self, controller) -> None:
        super().__init__(controller._preview._pdf_view)
        self._controller = controller

    def eventFilter(self, watched, event) -> bool:
        del watched
        if event.type() in {
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.KeyRelease,
        }:
            QTimer.singleShot(0, self._controller._nd_sync_from_preview_selection)
            QTimer.singleShot(30, self._controller._nd_sync_from_preview_selection)
        return False


def _shared_persian_font(settings) -> str:
    try:
        raw = settings.editor_persian_font_family
    except AttributeError:
        raw = settings._get(
            "editor",
            "persian_font_family",
            default=settings._get(
                "editor",
                "visual_persian_font_family",
                default=VisualPersianFontController.DEFAULT_FONT_FAMILY,
            ),
        )
    return VisualPersianFontController._resolve_installed_family(str(raw))


def _apply_editor_preferences(editor: LatexEditor, settings) -> None:
    family = _shared_persian_font(settings)
    source_highlighter = getattr(editor, "_highlighter", None)
    if source_highlighter is not None:
        source_highlighter._nd_persian_font_family = family
        try:
            source_highlighter.rehighlight()
        except RuntimeError:
            pass
    cursor_width = max(int(settings.editor_cursor_width), 1)
    editor.setCursorWidth(cursor_width)
    visual = getattr(editor, "_visual_editor", None)
    if visual is not None:
        visual.setCursorWidth(cursor_width)


def _cursor_flash_interval(editor) -> int:
    owner = editor if isinstance(editor, LatexEditor) else editor.parentWidget()
    settings = getattr(owner, "_app_settings", None)
    if settings is None:
        return 325
    try:
        flash_time = int(
            settings._get("editor", "cursor_flash_time_ms", default=650)
        )
    except (AttributeError, TypeError, ValueError):
        flash_time = 650
    return max(flash_time // 2, 150)


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Normalize PDF/editor text while preserving normalized-index to raw-index mapping."""
    output: list[str] = []
    raw_positions: list[int] = []
    last_was_space = False
    for raw_index, raw_character in enumerate(str(text or "")):
        if raw_character in {"\u200c", "\u200d", "\u200e", "\u200f", "\ufeff"}:
            continue
        expanded = unicodedata.normalize("NFKC", raw_character)
        for character in expanded:
            if character == "\u2029" or character.isspace():
                if output and not last_was_space:
                    output.append(" ")
                    raw_positions.append(raw_index)
                    last_was_space = True
                continue
            output.append(character)
            raw_positions.append(raw_index)
            last_was_space = False
    return "".join(output), raw_positions


def _find_normalized_span(raw_text: str, selected_text: str) -> tuple[int, int] | None:
    haystack, mapping = _normalize_with_map(raw_text)
    needle, _unused = _normalize_with_map(selected_text)
    needle = needle.strip()
    if not needle or not haystack or not mapping:
        return None
    start = haystack.casefold().find(needle.casefold())
    if start < 0:
        return None
    end_index = start + len(needle) - 1
    if end_index >= len(mapping):
        return None
    raw_start = mapping[start]
    raw_end = mapping[end_index] + 1
    if raw_end <= raw_start:
        return None
    return raw_start, raw_end


def _iter_quick_items(item: QQuickItem):
    yield item
    try:
        children = item.childItems()
    except (AttributeError, RuntimeError):
        return
    for child in children:
        yield from _iter_quick_items(child)


def _pdf_selection_item(view):
    cached = getattr(view, "_nd_pdf_selection_item", None)
    if cached is not None:
        try:
            cached.metaObject()
            return cached
        except RuntimeError:
            view._nd_pdf_selection_item = None
    root = view.rootObject()
    if not isinstance(root, QQuickItem):
        return None
    for item in _iter_quick_items(root):
        try:
            meta = item.metaObject()
            if meta.indexOfProperty("selectedText") >= 0:
                view._nd_pdf_selection_item = item
                return item
        except (AttributeError, RuntimeError):
            continue
    return None


def _read_pdf_selection(view) -> str:
    item = _pdf_selection_item(view)
    if item is None:
        return ""
    try:
        value = item.property("selectedText")
    except RuntimeError:
        view._nd_pdf_selection_item = None
        return ""
    return str(value or "").replace("\u2029", "\n").strip()


def _set_editor_selection_from_preview(editor: LatexEditor, selected_text: str) -> bool:
    """Map rendered PDF text back through Visual first, then Source as fallback."""
    visual = editor._visual_editor
    try:
        if getattr(editor, "_visual_dirty", False):
            editor._refresh_visual_projection()
    except (AttributeError, RuntimeError):
        pass

    visual_span = _find_normalized_span(visual.toPlainText(), selected_text)
    if visual_span is not None:
        start, end = visual_span
        try:
            anchor_location = visual.source_location_for_position(start)
            position_location = visual.source_location_for_position(end)
            visual_cursor = QTextCursor(visual.document())
            visual_cursor.setPosition(start)
            visual_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            editor._syncing_cursor_views = True
            try:
                visual.setTextCursor(visual_cursor)
                editor._set_source_selection_from_locations(
                    anchor_location, position_location
                )
            finally:
                editor._syncing_cursor_views = False
            editor.active_cursor_changed.emit()
            return True
        except (AttributeError, RuntimeError, TypeError, ValueError):
            editor._syncing_cursor_views = False

    source_span = _find_normalized_span(editor.toPlainText(), selected_text)
    if source_span is None:
        return False

    start, end = source_span
    source_cursor = QTextCursor(editor.document())
    source_cursor.setPosition(start)
    source_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    anchor_location = editor._source_location_for_position(start)
    position_location = editor._source_location_for_position(end)
    editor._syncing_cursor_views = True
    try:
        editor.setTextCursor(source_cursor)
        try:
            visual.set_selection_from_source_locations(
                anchor_location,
                position_location,
                ensure_visible=False,
            )
        except (AttributeError, RuntimeError):
            pass
    finally:
        editor._syncing_cursor_views = False
    editor.active_cursor_changed.emit()
    return True


def _install() -> None:
    if getattr(_install, "_done", False):
        return
    _install._done = True

    if not hasattr(YamlSettings, "editor_persian_font_family"):
        YamlSettings.editor_persian_font_family = property(
            lambda settings: str(
                settings._get(
                    "editor",
                    "persian_font_family",
                    default=settings._get(
                        "editor",
                        "visual_persian_font_family",
                        default=VisualPersianFontController.DEFAULT_FONT_FAMILY,
                    ),
                )
            ).strip()
            or VisualPersianFontController.DEFAULT_FONT_FAMILY
        )

    original_source_highlight = LatexSyntaxHighlighter.highlightBlock

    def source_highlight(highlighter, text: str) -> None:
        original_source_highlight(highlighter, text)
        family = str(
            getattr(highlighter, "_nd_persian_font_family", "") or ""
        ).strip()
        if not family:
            return
        for start, length in _persian_runs(text):
            try:
                character_format = QTextCharFormat(highlighter.format(start))
            except Exception:
                character_format = QTextCharFormat()
            _set_family(character_format, family)
            highlighter.setFormat(start, length, character_format)

    LatexSyntaxHighlighter.highlightBlock = source_highlight

    original_editor_init = LatexEditor.__init__
    original_editor_apply_settings = LatexEditor.apply_settings
    original_preview_highlight_text = LatexEditor.active_preview_highlight_text

    def editor_init(editor: LatexEditor, *args, **kwargs) -> None:
        original_editor_init(editor, *args, **kwargs)
        _apply_editor_preferences(editor, editor._app_settings)
        editor._nd_source_bookmark_underline = _BookmarkUnderlineOverlay(
            editor,
            editor._source_marker_y_for_location,
            lambda: list(editor._bookmarks),
        )
        editor._nd_visual_bookmark_underline = _BookmarkUnderlineOverlay(
            editor._visual_editor,
            editor._visual_editor.marker_y_for_source_location,
            lambda: list(editor._bookmarks),
        )

        def refresh_bookmark_visuals(*_args) -> None:
            for gutter_name in ("_source_bookmark_gutter", "_visual_bookmark_gutter"):
                gutter = getattr(editor, gutter_name, None)
                if gutter is not None:
                    gutter.update()
            editor._nd_source_bookmark_underline.refresh()
            editor._nd_visual_bookmark_underline.refresh()

        editor.bookmarks_changed.connect(refresh_bookmark_visuals)
        editor.verticalScrollBar().valueChanged.connect(refresh_bookmark_visuals)
        editor._visual_editor.verticalScrollBar().valueChanged.connect(
            refresh_bookmark_visuals
        )

    def editor_apply_settings(editor: LatexEditor, settings) -> None:
        original_editor_apply_settings(editor, settings)
        _apply_editor_preferences(editor, settings)

    def explicit_selection_preview_text(editor: LatexEditor) -> str:
        cursor = (
            editor._visual_editor.textCursor()
            if getattr(editor, "_edit_mode", "source") == "visual"
            else editor.textCursor()
        )
        if not cursor.hasSelection():
            return ""
        return str(original_preview_highlight_text(editor) or "")

    LatexEditor.__init__ = editor_init
    LatexEditor.apply_settings = editor_apply_settings
    LatexEditor.active_preview_highlight_text = explicit_selection_preview_text

    original_caret_init = PersistentCaretOverlay.__init__
    original_caret_paint = PersistentCaretOverlay.paintEvent

    def persistent_caret_init(overlay, editor) -> None:
        original_caret_init(overlay, editor)
        overlay._nd_blink_on = True
        timer = QTimer(overlay)
        timer.setTimerType(Qt.TimerType.CoarseTimer)
        timer.setInterval(_cursor_flash_interval(editor))

        def toggle() -> None:
            if editor.isVisible():
                overlay._nd_blink_on = not overlay._nd_blink_on
                overlay.update()

        timer.timeout.connect(toggle)
        timer.start()
        overlay._nd_blink_timer = timer

    def persistent_caret_paint(overlay, event) -> None:
        editor = overlay._editor
        if editor.hasFocus() and QApplication.activeWindow() is editor.window():
            original_caret_paint(overlay, event)
            return
        del event
        if not getattr(overlay, "_nd_blink_on", True) or not editor.isVisible():
            return
        cursor_rect = editor.cursorRect(editor.textCursor())
        x = cursor_rect.left() - overlay.geometry().left()
        if x < -2 or x > overlay.width() + 2:
            return
        if cursor_rect.bottom() < 0 or cursor_rect.top() > overlay.height():
            return
        top = max(cursor_rect.top(), 0)
        height = max(cursor_rect.height(), editor.fontMetrics().height(), 2)
        bottom = min(top + height, max(overlay.height() - 1, 0))
        if bottom <= top:
            return
        color = editor.palette().color(QPalette.ColorRole.Text)
        color.setAlpha(235)
        pen = QPen(color)
        pen.setWidth(max(int(editor.cursorWidth()), 1))
        painter = QPainter(overlay)
        painter.setPen(pen)
        draw_x = max(0, min(int(x), max(overlay.width() - 1, 0)))
        painter.drawLine(draw_x, top, draw_x, bottom)
        painter.end()

    PersistentCaretOverlay.__init__ = persistent_caret_init
    PersistentCaretOverlay.paintEvent = persistent_caret_paint

    original_workspace_init = WorkspaceInteractionController.__init__

    def workspace_init(controller, *args, **kwargs) -> None:
        original_workspace_init(controller, *args, **kwargs)
        preview = controller._preview
        overlay = getattr(preview, "_nd_preview_caret_overlay", None)
        if overlay is None:
            overlay = _PreviewCaretOverlay(preview)
            preview._nd_preview_caret_overlay = overlay

        renderer = getattr(controller._window, "_renderer", None)
        if renderer is not None:
            def update_preview_caret(page: int, x: float, y: float, item=overlay) -> None:
                item.set_target(page, x, y)
            renderer.source_position_mapped.connect(update_preview_caret)
            preview._nd_preview_caret_callback = update_preview_caret

        view = preview._pdf_view
        controller._nd_last_preview_selected_text = ""
        controller._nd_preview_selection_syncing = False
        event_filter = _PreviewSelectionEventFilter(controller)
        view.installEventFilter(event_filter)
        controller._nd_preview_selection_event_filter = event_filter

        for delay in (0, 100, 400):
            QTimer.singleShot(delay, controller._nd_bind_preview_selection_signal)

    def bind_preview_selection_signal(controller) -> None:
        view = controller._preview._pdf_view
        if bool(getattr(view, "_nd_pdf_selection_signal_bound", False)):
            return
        item = _pdf_selection_item(view)
        if item is None:
            return
        signal = getattr(item, "selectedTextChanged", None)
        if signal is None:
            return
        try:
            signal.connect(controller._nd_sync_from_preview_selection)
            view._nd_pdf_selection_signal_bound = True
        except (RuntimeError, TypeError):
            pass

    def sync_from_preview_selection(controller) -> None:
        if bool(getattr(controller, "_nd_preview_selection_syncing", False)):
            return
        view = controller._preview._pdf_view
        selected_text = _read_pdf_selection(view)
        if not selected_text:
            return
        if selected_text == getattr(controller, "_nd_last_preview_selected_text", ""):
            return
        editor = controller._editor_panel.current_editor()
        if not isinstance(editor, LatexEditor):
            return
        controller._nd_preview_selection_syncing = True
        try:
            if not _set_editor_selection_from_preview(editor, selected_text):
                return
            controller._nd_last_preview_selected_text = selected_text
            controller._schedule_preview_highlight()
        finally:
            controller._nd_preview_selection_syncing = False

    def sync_preview_highlight(controller) -> None:
        editor = controller._editor_panel.current_editor()
        text = ""
        if isinstance(editor, LatexEditor):
            try:
                text = str(editor.active_preview_highlight_text() or "")
            except (AttributeError, RuntimeError):
                text = ""
        view = getattr(controller._preview, "_pdf_view", None)
        if view is None:
            return
        root = view.rootObject()
        if root is None:
            return
        if text == getattr(controller, "_last_highlight_text", None):
            overlay = getattr(controller._preview, "_nd_preview_caret_overlay", None)
            if overlay is not None:
                overlay.update()
            return
        root.setProperty("editHighlightText", text)
        view._nd_selection_highlight_active = bool(text.strip())
        controller._last_highlight_text = text
        if not text.strip():
            controller._nd_last_preview_selected_text = ""
        overlay = getattr(controller._preview, "_nd_preview_caret_overlay", None)
        if overlay is not None:
            overlay.update()

    WorkspaceInteractionController.__init__ = workspace_init
    WorkspaceInteractionController._nd_bind_preview_selection_signal = (
        bind_preview_selection_signal
    )
    WorkspaceInteractionController._nd_sync_from_preview_selection = (
        sync_from_preview_selection
    )
    WorkspaceInteractionController._sync_preview_highlight = sync_preview_highlight


_install()
