"""Keep Navigator selection centered on the Source/Visual click target."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QColor, QPalette

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver,
)
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.window.main.navigator_active_selection_controller import (
    NavigatorActiveSelectionController,
)
from nd_mind_mirror.ui.window.main.navigator_path_reveal_controller import (
    NavigatorPathRevealController,
)


class NavigatorStrictActiveSelectionController(
    NavigatorActiveSelectionController
):
    """Center and highlight the file represented by each Source/Visual click."""

    _GRAPHIC_COMMANDS = {"includegraphics", "includepdf"}

    def __init__(self, editor_panel, file_system_panel, parent=None) -> None:
        """Install event-driven path reveal plus Source/Visual click synchronization."""
        self._editor_panel = editor_panel
        self._click_editor = None
        self._source_viewport = None
        self._visual_viewport = None
        self._reference_resolver = WorkspaceReferenceResolver(
            file_system_panel._root_path
        )
        self._occurrence_cache_key: tuple[int, int, str] | None = None
        self._occurrence_cache: tuple[ReferenceOccurrence, ...] = ()

        super().__init__(editor_panel, file_system_panel, parent)
        self._tree = file_system_panel._tree
        self._path_reveal_controller = NavigatorPathRevealController(
            file_system_panel,
            self,
        )
        self._path_reveal_controller.path_revealed.connect(
            self._on_path_revealed
        )
        self._configure_selection_palette()
        self._attach_current_editor()

        current = editor_panel.current_path()
        if current is not None:
            self._reveal_centered(current)

    @Slot(str, str)
    def _on_current_document_changed(self, path: str, _content: str) -> None:
        """Attach the new editor and reveal its file when the model is ready."""
        self._attach_current_editor()
        if path:
            self._reveal_centered(path)

    def eventFilter(self, watched, event) -> bool:
        """Recenter Navigator after every normal Source or Visual left click."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
            and watched in {self._source_viewport, self._visual_viewport}
        ):
            target = self._target_for_click(watched, event.position().toPoint())
            if target is not None:
                self._reveal_centered(target)
        return super().eventFilter(watched, event)

    def _attach_current_editor(self) -> None:
        """Observe only the current editor's Source and Visual viewports."""
        self._detach_editor_filters()
        editor = self._editor_panel.current_editor()
        if editor is None:
            return

        self._click_editor = editor
        source_viewport = getattr(editor, "viewport", None)
        if callable(source_viewport):
            self._source_viewport = source_viewport()
            self._source_viewport.installEventFilter(self)

        visual = getattr(editor, "_visual_editor", None)
        visual_viewport = getattr(visual, "viewport", None)
        if callable(visual_viewport):
            self._visual_viewport = visual_viewport()
            self._visual_viewport.installEventFilter(self)

        self._occurrence_cache_key = None
        self._occurrence_cache = ()

    def _detach_editor_filters(self) -> None:
        """Release viewport filters before switching to another editor tab."""
        for viewport in (self._source_viewport, self._visual_viewport):
            if viewport is None:
                continue
            try:
                viewport.removeEventFilter(self)
            except RuntimeError:
                pass
        self._source_viewport = None
        self._visual_viewport = None
        self._click_editor = None

    def _target_for_click(self, watched, point) -> Path | None:
        """Return the clicked graphic file, otherwise the current editor file."""
        editor = self._click_editor
        current_path = self._editor_panel.current_path()
        if editor is None or current_path is None:
            return None

        if isinstance(editor, LatexEditor):
            if watched is self._source_viewport:
                graphic = self._source_graphic_at_point(editor, point)
                if graphic is not None:
                    return graphic
            elif watched is self._visual_viewport:
                graphic = self._visual_graphic_at_point(editor, point)
                if graphic is not None:
                    return graphic

        return Path(current_path).expanduser().resolve(strict=False)

    def _source_graphic_at_point(self, editor: LatexEditor, point) -> Path | None:
        """Resolve an includegraphics/includepdf command under a Source click."""
        cursor = editor.cursorForPosition(point)
        position = int(cursor.position())
        for occurrence in self._graphic_occurrences(editor):
            if occurrence.command_start <= position <= occurrence.command_end:
                return occurrence.target_path
        return None

    def _graphic_occurrences(
        self,
        editor: LatexEditor,
    ) -> tuple[ReferenceOccurrence, ...]:
        """Cache local graphic-reference parsing by document revision and path."""
        source_path = editor.source_path
        revision = int(editor.document().revision())
        key = (id(editor), revision, str(source_path))
        if key == self._occurrence_cache_key:
            return self._occurrence_cache

        self._reference_resolver.set_default_path(
            self._file_system_panel._root_path
        )
        occurrences = self._reference_resolver.occurrences(
            editor.toPlainText(),
            source_path,
            require_exists=True,
        )
        self._occurrence_cache = tuple(
            item
            for item in occurrences
            if item.command in self._GRAPHIC_COMMANDS
            and item.target_path is not None
        )
        self._occurrence_cache_key = key
        return self._occurrence_cache

    def _visual_graphic_at_point(self, editor: LatexEditor, point) -> Path | None:
        """Resolve the actual raster/PDF represented by a Visual graphic block."""
        visual = getattr(editor, "_visual_editor", None)
        if visual is None:
            return None

        cursor = visual.cursorForPosition(point)
        image_path = self._visual_resource_path(cursor)
        if image_path is not None:
            return image_path

        metadata = cursor.block().userData()
        if getattr(metadata, "kind", "") != "graphic":
            return None
        raw_target = str(getattr(metadata, "display", "")).strip()
        if not raw_target:
            return None

        self._reference_resolver.set_default_path(
            self._file_system_panel._root_path
        )
        return self._reference_resolver.resolve(
            raw_target,
            editor.source_path,
            command="includegraphics",
            require_exists=True,
        )

    @staticmethod
    def _visual_resource_path(cursor) -> Path | None:
        """Extract an existing file path from the Visual ndgraphic image resource."""
        character_format = cursor.charFormat()
        if not character_format.isImageFormat():
            return None
        name = character_format.toImageFormat().name()
        prefix = "ndgraphic:"
        if not name.startswith(prefix):
            return None
        value = name[len(prefix):]
        path_text, separator, timestamp = value.rpartition(":")
        if separator and timestamp.isdigit():
            value = path_text
        if not value:
            return None
        path = Path(value).expanduser().resolve(strict=False)
        return path if path.is_file() else None

    def _reveal_centered(self, path: str | Path) -> None:
        """Request one path; the model signals when it can be selected."""
        self._path_reveal_controller.reveal(path)

    def _on_path_revealed(self, _path: str) -> None:
        """Center the already selected row horizontally after successful reveal."""
        index = self._tree.currentIndex()
        if not index.isValid():
            return
        self._center_index_horizontally(index)

    def _center_index_horizontally(self, index) -> None:
        """Center deep tree labels horizontally when the tree can scroll sideways."""
        scrollbar = self._tree.horizontalScrollBar()
        if scrollbar.maximum() <= scrollbar.minimum():
            return
        rect = self._tree.visualRect(index)
        if not rect.isValid():
            return
        item_width = max(int(self._tree.sizeHintForIndex(index).width()), 1)
        content_center = scrollbar.value() + rect.left() + item_width // 2
        desired = content_center - self._tree.viewport().width() // 2
        scrollbar.setValue(
            max(scrollbar.minimum(), min(desired, scrollbar.maximum()))
        )

    def _configure_selection_palette(self) -> None:
        """Keep selection blue with white text while keyboard focus is in Editor."""
        palette = self._tree.palette()
        blue = QColor("#2f6fdb")
        white = QColor("#ffffff")
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
        ):
            palette.setColor(group, QPalette.ColorRole.Highlight, blue)
            palette.setColor(
                group,
                QPalette.ColorRole.HighlightedText,
                white,
            )
        self._tree.setPalette(palette)
