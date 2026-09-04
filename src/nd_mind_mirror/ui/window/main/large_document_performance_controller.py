"""Install safe large-document performance policies that do not virtualize Source."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPalette

from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.panel.file_system.file_system_panel import FileSystemPanel
from nd_mind_mirror.ui.panel.structure.latex_structure_panel import LatexStructurePanel
from nd_mind_mirror.ui.search.thread.file_search_index_thread import FileSearchIndexThread
from nd_mind_mirror.ui.search.window.search_window import SearchWindow
from nd_mind_mirror.ui.window.main.late_runtime_fixes import LateRuntimeFixes
from nd_mind_mirror.ui.window.main.logical_line_number_overlay import (
    LogicalLineNumberOverlay,
)
from nd_mind_mirror.ui.window.main.main_window import MainWindow


class LargeDocumentPerformanceController:
    """Install performance policies that keep the canonical Source complete."""

    _hook_installed = False
    _runtime_installed = False
    _SOURCE_VIRTUAL_THRESHOLD_CHARS = 80_000
    _SMALL_PREVIEW_THRESHOLD_CHARS = 60_000
    _SMALL_VISUAL_EMIT_MS = 55
    _SMALL_PREVIEW_DEBOUNCE_MS = 35

    @classmethod
    def install_startup_hook(cls) -> None:
        """Run performance policies after legacy class setup and before widgets exist."""
        if cls._hook_installed:
            return
        original_install = LateRuntimeFixes.install_class_patches

        def install_class_patches(_late_cls) -> None:
            original_install()
            cls._install_runtime_patches()

        LateRuntimeFixes.install_class_patches = classmethod(install_class_patches)
        cls._hook_installed = True

    @classmethod
    def _install_runtime_patches(cls) -> None:
        """Install only policies that do not replace or window canonical Source."""
        if cls._runtime_installed:
            return
        cls._install_structure_idle_fast_path()
        cls._install_preview_fast_path()
        cls._install_preview_disable_cleanup()
        cls._install_navigator_density()
        cls._install_double_shift_focus_fix()
        cls._install_global_line_number_overlay()
        cls._runtime_installed = True

    @classmethod
    def _install_structure_idle_fast_path(cls) -> None:
        """Skip a full structure rescan when ordinary prose changes inside one line."""
        original = LatexStructurePanel.set_document
        tokens = (
            "\\part",
            "\\chapter",
            "\\section",
            "\\subsection",
            "\\subsubsection",
            "\\paragraph",
            "\\subparagraph",
            "\\includegraphics",
            "\\caption",
            "\\begin{figure",
            "\\end{figure",
        )

        def set_document(
            panel: LatexStructurePanel,
            path,
            source: str,
            immediate: bool = False,
        ) -> None:
            value = str(source)
            try:
                file_path = Path(path).expanduser().resolve()
            except OSError:
                original(panel, path, source, immediate)
                return
            old = str(getattr(panel, "_source", ""))
            same_path = getattr(panel, "_path", None) == file_path
            if (
                not immediate
                and same_path
                and len(value) >= cls._SOURCE_VIRTUAL_THRESHOLD_CHARS
                and old
                and not cls._structure_change_requires_rescan(old, value, tokens)
            ):
                # Keep the complete source even when rebuilding the tree can wait.
                panel._source = value
                panel._path = file_path
                panel._label.setText(f"Structure — {file_path.name}")
                return
            original(panel, path, value, immediate)

        LatexStructurePanel.set_document = set_document

    @staticmethod
    def _structure_change_requires_rescan(
        old: str,
        new: str,
        tokens: tuple[str, ...],
    ) -> bool:
        if old == new:
            return False
        limit = min(len(old), len(new))
        prefix = 0
        chunk = 4096
        while (
            prefix + chunk <= limit
            and old[prefix : prefix + chunk] == new[prefix : prefix + chunk]
        ):
            prefix += chunk
        while prefix < limit and old[prefix] == new[prefix]:
            prefix += 1

        suffix_limit = min(len(old) - prefix, len(new) - prefix)
        suffix = 0
        while (
            suffix + chunk <= suffix_limit
            and old[len(old) - suffix - chunk : len(old) - suffix]
            == new[len(new) - suffix - chunk : len(new) - suffix]
        ):
            suffix += chunk
        while (
            suffix < suffix_limit
            and old[len(old) - suffix - 1] == new[len(new) - suffix - 1]
        ):
            suffix += 1

        old_end = len(old) - suffix
        new_end = len(new) - suffix
        old_changed = old[prefix:old_end]
        new_changed = new[prefix:new_end]
        if "\n" in old_changed or "\n" in new_changed:
            return True
        if "\\" in old_changed or "\\" in new_changed:
            return True

        def line_context(text: str, start: int, end: int) -> str:
            left = text.rfind("\n", 0, start) + 1
            right = text.find("\n", end)
            if right < 0:
                right = len(text)
            return text[left:right]

        context = (
            line_context(old, prefix, old_end)
            + "\n"
            + line_context(new, prefix, new_end)
        )
        return any(token in context for token in tokens)

    @classmethod
    def _install_preview_fast_path(cls) -> None:
        """Use the existing coalesced Preview/Visual paths with low small-file latency."""
        original_compile = getattr(
            LateRuntimeFixes,
            "_original_compile_pending_source",
            None,
        )
        if callable(original_compile):
            LatexRenderer._compile_pending_source = original_compile

        original_render = LatexRenderer.render
        original_visual_schedule = LatexVisualEditor._schedule_source_emit

        def render(
            renderer: LatexRenderer,
            source: str,
            source_path=None,
            immediate: bool = False,
        ) -> None:
            original_render(
                renderer,
                source,
                source_path=source_path,
                immediate=immediate,
            )
            if (
                renderer.enabled
                and not immediate
                and len(str(source)) < cls._SMALL_PREVIEW_THRESHOLD_CHARS
                and renderer._timer.isActive()
            ):
                renderer._timer.setInterval(cls._SMALL_PREVIEW_DEBOUNCE_MS)
                renderer._timer.start()

        def schedule_visual_source_emit(editor: LatexVisualEditor) -> None:
            original_visual_schedule(editor)
            if (
                not editor._loading
                and editor._has_loaded_source
                and int(getattr(editor, "_source_char_count", 0))
                < cls._SMALL_PREVIEW_THRESHOLD_CHARS
                and editor._emit_timer.isActive()
            ):
                editor._emit_timer.setInterval(cls._SMALL_VISUAL_EMIT_MS)
                editor._emit_timer.start()

        LatexRenderer.render = render
        LatexVisualEditor._schedule_source_emit = schedule_visual_source_emit

    @classmethod
    def _install_preview_disable_cleanup(cls) -> None:
        """Cancel Preview-only timers and caches while Preview is hidden."""
        original_set_preview_enabled = MainWindow._set_preview_enabled
        original_sync_dependencies = MainWindow._sync_preview_dependency_changes

        def set_preview_enabled(
            window: MainWindow,
            enabled: bool,
            refresh: bool = True,
        ) -> None:
            original_set_preview_enabled(window, enabled, refresh)
            if bool(enabled):
                return
            for name in (
                "_preview_edit_highlight_timer",
                "_graphic_preview_refresh_timer",
            ):
                timer = getattr(window, name, None)
                if timer is not None:
                    timer.stop()
            window._pending_preview_edit_highlight = ""
            window._last_preview_edit_highlight = ""
            window._preview_dependency_signatures = {}

        def sync_preview_dependency_changes(window: MainWindow) -> None:
            if not bool(getattr(window, "_preview_enabled", False)):
                return
            original_sync_dependencies(window)

        MainWindow._set_preview_enabled = set_preview_enabled
        MainWindow._sync_preview_dependency_changes = sync_preview_dependency_changes

    @classmethod
    def _install_navigator_density(cls) -> None:
        """Use compact icons and a clear hierarchy indent in the Navigator."""
        original_init = FileSystemPanel.__init__
        original_apply = FileSystemPanel.apply_settings

        def init(panel: FileSystemPanel, parent=None) -> None:
            original_init(panel, parent)
            panel._tree.setIconSize(QSize(14, 14))
            panel._tree.setIndentation(20)

        def apply_settings(
            panel: FileSystemPanel,
            indent_width: int,
            root_path,
            ignore_file_path,
            row_height: int = 24,
            latex_templates=None,
        ) -> None:
            original_apply(
                panel,
                indent_width=max(int(indent_width), 20),
                root_path=root_path,
                ignore_file_path=ignore_file_path,
                row_height=row_height,
                latex_templates=latex_templates,
            )
            panel._tree.setIconSize(QSize(14, 14))
            panel._tree.setIndentation(max(int(indent_width), 20))

        FileSystemPanel.__init__ = init
        FileSystemPanel.apply_settings = apply_settings

    @classmethod
    def _install_double_shift_focus_fix(cls) -> None:
        """Focus search immediately and refresh the filename index asynchronously."""
        original_apply_index = SearchWindow._apply_index

        def rebuild_index(window: SearchWindow) -> None:
            window._index_generation += 1
            generation = window._index_generation
            same_root_index = (
                bool(window._index_ready)
                and bool(window._search_index)
                and getattr(window, "_nd_index_root_path", window._root_path)
                == window._root_path
            )
            window._generation += 1
            window._debounce_timer.stop()

            for thread in list(window._threads):
                if thread.isRunning():
                    thread.requestInterruption()

            old_index_thread = window._index_thread
            if old_index_thread is not None and old_index_thread.isRunning():
                old_index_thread.requestInterruption()

            if not same_root_index:
                window._index_ready = False
                window._search_index = []
                window._status_label.setText("Indexing search root...")
            elif not window._search_edit.text().strip():
                window._status_label.setText("Refreshing search index...")

            thread = FileSearchIndexThread(
                generation=generation,
                root_path=window._root_path,
                ignore_file_path=window._ignore_file_path,
                parent=window,
            )
            window._index_thread = thread
            thread.index_ready.connect(window._apply_index)
            thread.finished.connect(
                lambda item=thread: window._remove_index_thread(item)
            )
            thread.start()

        def apply_index(
            window: SearchWindow,
            generation: int,
            entries: object,
        ) -> None:
            original_apply_index(window, generation, entries)
            if generation == window._index_generation:
                window._nd_index_root_path = window._root_path

        def show_and_focus(window: SearchWindow) -> None:
            window._center_on_parent()
            window.show()
            window._center_on_parent()
            window.raise_()
            window.activateWindow()
            window._search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            window._search_edit.selectAll()
            if window._search_edit.text().strip():
                window._schedule_search()

            current_index_thread = window._index_thread
            if current_index_thread is None or not current_index_thread.isRunning():
                QTimer.singleShot(120, window.rebuild_index)

        SearchWindow.rebuild_index = rebuild_index
        SearchWindow._apply_index = apply_index
        SearchWindow.show_and_focus = show_and_focus

    @classmethod
    def _install_global_line_number_overlay(cls) -> None:
        """Keep line-number overlay sizing and painting stable for complete Source."""
        def update_width(overlay: LogicalLineNumberOverlay, *args) -> None:
            del args
            editor = overlay._editor
            total = max(editor.document().blockCount(), 1)
            digits = max(2, len(str(total)))
            metrics = QFontMetricsF(editor.font())
            desired = max(
                overlay._MIN_WIDTH,
                int(math.ceil(metrics.horizontalAdvance("9" * digits)))
                + overlay._HORIZONTAL_PADDING,
            )
            if desired != overlay._gutter_width:
                overlay._gutter_width = desired
                margins = overlay._base_margins
                editor.setViewportMargins(
                    margins.left() + overlay._gutter_width,
                    margins.top(),
                    margins.right(),
                    margins.bottom(),
                )
            overlay._position()

        def paint_event(overlay: LogicalLineNumberOverlay, event) -> None:
            del event
            editor = overlay._editor
            painter = QPainter(overlay)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            palette = editor.palette()
            color = palette.color(QPalette.ColorRole.PlaceholderText)
            if not color.isValid():
                color = QColor("#7a7a7a")
            painter.setPen(color)
            font = editor.font()
            point_size = font.pointSizeF()
            if point_size > 0:
                font.setPointSizeF(max(point_size * 0.78, 7.0))
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            viewport = editor.viewport()
            first_cursor = editor.cursorForPosition(QPoint(2, 0))
            block = first_cursor.block()
            if block.previous().isValid():
                block = block.previous()
            viewport_height = float(viewport.height())
            while block.isValid():
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                rectangle = editor.cursorRect(cursor)
                top = float(rectangle.top())
                if top > viewport_height + metrics.height():
                    break
                if top + metrics.height() >= 0:
                    text_rect = QRectF(
                        0.0,
                        top,
                        float(max(overlay._gutter_width - 6, 1)),
                        float(max(metrics.height(), rectangle.height())),
                    )
                    painter.drawText(
                        text_rect,
                        int(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignTop
                        ),
                        str(block.blockNumber() + 1),
                    )
                block = block.next()

        LogicalLineNumberOverlay._update_width = update_width
        LogicalLineNumberOverlay.paintEvent = paint_event
