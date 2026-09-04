"""Install persistent editor visuals, logical line numbers, and shared source indentation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.window.main.logical_line_number_overlay import LogicalLineNumberOverlay
from nd_mind_mirror.ui.window.main.persistent_caret_overlay import PersistentCaretOverlay
from nd_mind_mirror.ui.window.main.source_tab_indentation_controller import SourceTabIndentationController


class PersistentEditorVisuals:
    """Attach editor visuals and shared source behavior before document tabs are created."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        """Install construction and source-key hooks exactly once before tabs are created."""
        if cls._installed:
            return

        SourceTabIndentationController.install()

        original_latex_init: Callable = LatexEditor.__init__
        original_yaml_init: Callable = YamlEditor.__init__
        original_generic_init: Callable = GenericTextEditor.__init__

        def latex_init(editor: LatexEditor, *args, **kwargs) -> None:
            """Initialize LaTeX then attach source numbers plus Source/Visual carets."""
            original_latex_init(editor, *args, **kwargs)
            cls._attach_latex_features(editor)

        def yaml_init(editor: YamlEditor, *args, **kwargs) -> None:
            """Initialize YAML then attach one logical source-line-number gutter."""
            original_yaml_init(editor, *args, **kwargs)
            cls._attach_source_line_numbers(editor)

        def generic_init(editor: GenericTextEditor, *args, **kwargs) -> None:
            """Initialize a generic text source then attach logical line numbers."""
            original_generic_init(editor, *args, **kwargs)
            cls._attach_source_line_numbers(editor)

        LatexEditor.__init__ = latex_init
        YamlEditor.__init__ = yaml_init
        GenericTextEditor.__init__ = generic_init

        # Keep legacy adaptations in one place instead of stacking migration-
        # specific patch modules throughout the startup path.
        from nd_mind_mirror.ui.window.main.runtime_fixes import LateRuntimeFixes
        from nd_mind_mirror.ui.window.main.image_sequence_fix import ImageSequenceFix
        from nd_mind_mirror.ui.window.main.editor_runtime_extensions import (
            EditorRuntimeExtensions,
        )
        from nd_mind_mirror.ui.window.main.workspace_reference_controller import (
            WorkspaceReferenceController,
        )

        LateRuntimeFixes.install()
        ImageSequenceFix.install()
        EditorRuntimeExtensions.install()
        cls._install_selection_bookmark_visuals()
        WorkspaceReferenceController.install()
        cls._installed = True

    @staticmethod
    def _bookmark_locations(
        bookmark: dict[str, object],
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return a persisted selection range; line-only bookmarks are intentionally invalid."""
        try:
            anchor = (
                max(int(bookmark["selection_anchor_line"]), 1),
                max(int(bookmark["selection_anchor_column"]), 1),
            )
            position = (
                max(int(bookmark["selection_position_line"]), 1),
                max(int(bookmark["selection_position_column"]), 1),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return None if anchor == position else (anchor, position)

    @staticmethod
    def _active_selection_locations(
        editor: LatexEditor,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return the currently selected Source range in canonical source coordinates."""
        if getattr(editor, "_edit_mode", "source") == "visual":
            cursor = editor._visual_editor.textCursor()
            if not cursor.hasSelection():
                return None
            anchor, position = editor._visual_editor.source_selection_locations()
        else:
            cursor = editor.textCursor()
            if not cursor.hasSelection():
                return None
            anchor = editor._source_location_for_position(cursor.anchor())
            position = editor._source_location_for_position(cursor.position())
        return None if anchor == position else (anchor, position)

    @staticmethod
    def _bookmark_color() -> QColor:
        """Use a visible but deliberately soft yellow for saved selections."""
        color = QColor("#ffd54f")
        color.setAlpha(92)
        return color

    @classmethod
    def _source_bookmark_selections(cls, editor: LatexEditor):
        selections = []
        color = cls._bookmark_color()
        for bookmark in getattr(editor, "_bookmarks", []):
            locations = cls._bookmark_locations(bookmark)
            if locations is None:
                continue
            anchor, position = locations
            first = editor._source_position_for_location(anchor)
            second = editor._source_position_for_location(position)
            if first == second:
                continue
            cursor = QTextCursor(editor.document())
            cursor.setPosition(first)
            cursor.setPosition(second, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(color)
            selections.append(selection)
        return selections

    @classmethod
    def _refresh_visual_bookmark_highlights(cls, editor: LatexEditor) -> None:
        visual = getattr(editor, "_visual_editor", None)
        if visual is None:
            return
        selections = []
        color = cls._bookmark_color()
        for bookmark in getattr(editor, "_bookmarks", []):
            locations = cls._bookmark_locations(bookmark)
            if locations is None:
                continue
            anchor, position = locations
            first = visual.visual_position_for_source_location(*anchor)
            second = visual.visual_position_for_source_location(*position)
            if first == second:
                continue
            cursor = QTextCursor(visual.document())
            cursor.setPosition(first)
            cursor.setPosition(second, QTextCursor.MoveMode.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(color)
            selections.append(selection)
        visual.setExtraSelections(selections)

    @classmethod
    def _refresh_bookmark_highlights(cls, editor: LatexEditor) -> None:
        editor._highlight_current_line()
        cls._refresh_visual_bookmark_highlights(editor)

    @staticmethod
    def _hide_bookmark_gutters(editor: LatexEditor) -> None:
        """The old line bookmark ribbons no longer exist in the UI."""
        for name in ("_source_bookmark_gutter", "_visual_bookmark_gutter"):
            gutter = getattr(editor, name, None)
            if gutter is not None:
                gutter.hide()
                gutter.setFixedWidth(0)

    @staticmethod
    def _apply_bookmark_free_padding(editor: LatexEditor, app_settings) -> None:
        """Remove the 18 px that was reserved exclusively for the old bookmark gutter."""
        editor.apply_content_padding(
            top=app_settings.editor_source_padding_top,
            left=app_settings.editor_source_padding_left,
            right=app_settings.editor_source_padding_right,
        )
        visual = getattr(editor, "_visual_editor", None)
        if visual is not None:
            visual.apply_content_padding(
                top=app_settings.editor_visual_padding_top,
                left=app_settings.editor_visual_padding_left,
                right=app_settings.editor_visual_padding_right,
            )

    @staticmethod
    def _collapse_active_selection(editor: LatexEditor) -> None:
        active = (
            editor._visual_editor
            if getattr(editor, "_edit_mode", "source") == "visual"
            else editor
        )
        cursor = active.textCursor()
        cursor.setPosition(cursor.position())
        active.setTextCursor(cursor)

    @classmethod
    def _install_selection_bookmark_visuals(cls) -> None:
        """Replace line bookmarks with persistent highlighted selection bookmarks."""
        from nd_mind_mirror.ui.window.main.editor_interaction_enhancements import (
            EditorInteractionEnhancements,
        )
        from nd_mind_mirror.ui.window.main.main_window import MainWindow

        original_highlight: Callable = LatexEditor._highlight_current_line
        original_set_bookmarks: Callable = LatexEditor.set_bookmarks
        original_toggle_bookmark: Callable = LatexEditor._toggle_bookmark
        original_refresh_visual_projection: Callable = LatexEditor._refresh_visual_projection
        original_apply_settings: Callable = LatexEditor.apply_settings
        original_create_actions: Callable = MainWindow._create_actions

        def highlight_current_line(editor: LatexEditor) -> None:
            original_highlight(editor)
            selections = list(editor.extraSelections())
            selections.extend(cls._source_bookmark_selections(editor))
            editor.setExtraSelections(selections)

        def update_bookmark_gutters(editor: LatexEditor) -> None:
            cls._hide_bookmark_gutters(editor)
            cls._refresh_bookmark_highlights(editor)

        def position_bookmark_gutters(editor: LatexEditor) -> None:
            cls._hide_bookmark_gutters(editor)

        def set_bookmarks(editor: LatexEditor, bookmarks) -> None:
            selection_bookmarks = [
                dict(bookmark)
                for bookmark in (bookmarks or [])
                if isinstance(bookmark, dict)
                and cls._bookmark_locations(bookmark) is not None
            ]
            original_set_bookmarks(editor, selection_bookmarks)
            cls._refresh_bookmark_highlights(editor)

        def toggle_bookmark(editor: LatexEditor, line: int, column: int) -> None:
            locations = cls._active_selection_locations(editor)
            if locations is None:
                return
            anchor, position = locations
            start = min(
                (anchor, position),
                key=lambda value: editor._source_position_for_location(value),
            )
            original_toggle_bookmark(editor, int(start[0]), int(start[1]))
            cls._collapse_active_selection(editor)
            cls._refresh_bookmark_highlights(editor)

        def toggle_bookmark_at_cursor(editor: LatexEditor) -> None:
            locations = cls._active_selection_locations(editor)
            if locations is None:
                return
            anchor, position = locations
            start = min(
                (anchor, position),
                key=lambda value: editor._source_position_for_location(value),
            )
            editor._toggle_bookmark(int(start[0]), int(start[1]))

        def refresh_visual_projection(editor: LatexEditor) -> None:
            original_refresh_visual_projection(editor)
            cls._refresh_visual_bookmark_highlights(editor)

        def apply_settings(editor: LatexEditor, app_settings) -> None:
            original_apply_settings(editor, app_settings)
            cls._apply_bookmark_free_padding(editor, app_settings)
            cls._hide_bookmark_gutters(editor)

        def append_bookmark_action(menu, editor, line: int, column: int) -> None:
            menu.addSeparator()
            action = menu.addAction("Bookmark")
            action.triggered.connect(
                lambda _checked=False, item=editor, row=int(line), col=int(column):
                item._toggle_bookmark(row, col)
            )

        def create_actions(window: MainWindow) -> None:
            original_create_actions(window)
            action = getattr(window, "_toggle_bookmark_action", None)
            if action is not None:
                action.setText("Bookmark Selection")

        LatexEditor._highlight_current_line = highlight_current_line
        LatexEditor._update_bookmark_gutters = update_bookmark_gutters
        LatexEditor._position_bookmark_gutters = position_bookmark_gutters
        LatexEditor.set_bookmarks = set_bookmarks
        LatexEditor._toggle_bookmark = toggle_bookmark
        LatexEditor.toggle_bookmark_at_cursor = toggle_bookmark_at_cursor
        LatexEditor._refresh_visual_projection = refresh_visual_projection
        LatexEditor.apply_settings = apply_settings
        EditorInteractionEnhancements._append_bookmark_action = staticmethod(
            append_bookmark_action
        )
        MainWindow._create_actions = create_actions

    @staticmethod
    def _attach_latex_features(editor: LatexEditor) -> None:
        """Attach persistent carets and one logical-line-number gutter to LaTeX Source."""
        editor._nd_source_persistent_caret = PersistentCaretOverlay(editor)
        editor._nd_visual_persistent_caret = PersistentCaretOverlay(editor._visual_editor)
        PersistentEditorVisuals._attach_source_line_numbers(editor)
        PersistentEditorVisuals._hide_bookmark_gutters(editor)
        PersistentEditorVisuals._apply_bookmark_free_padding(
            editor,
            editor._app_settings,
        )
        PersistentEditorVisuals._refresh_bookmark_highlights(editor)

    @staticmethod
    def _attach_source_line_numbers(editor) -> None:
        """Attach one gutter that numbers QTextDocument blocks, never soft-wrap rows."""
        if getattr(editor, "_nd_logical_line_numbers", None) is not None:
            return
        editor._nd_logical_line_numbers = LogicalLineNumberOverlay(editor)
