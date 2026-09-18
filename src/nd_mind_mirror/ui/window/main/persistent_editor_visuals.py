"""Install persistent editor visuals without owning bookmark behavior."""

from __future__ import annotations

from collections.abc import Callable

from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.window.main.logical_line_number_overlay import (
    LogicalLineNumberOverlay,
)
from nd_mind_mirror.ui.window.main.persistent_caret_overlay import (
    PersistentCaretOverlay,
)
from nd_mind_mirror.ui.window.main.source_tab_indentation_controller import (
    SourceTabIndentationController,
)


class PersistentEditorVisuals:
    """Attach persistent carets, line numbers, and shared Source presentation.

    Bookmark ownership intentionally does not live here.  Range bookmarks are
    implemented by RangeBookmarkEditorMixin for both regular and virtualized
    large LaTeX editors.  Keeping this startup visual layer bookmark-free avoids
    re-installing the retired line/selection bookmark system over the canonical
    character-range model.
    """

    _installed = False

    @classmethod
    def install(cls) -> None:
        """Install visual construction hooks exactly once before tabs are created."""
        if cls._installed:
            return

        SourceTabIndentationController.install()

        original_latex_init: Callable = LatexEditor.__init__
        original_yaml_init: Callable = YamlEditor.__init__
        original_generic_init: Callable = GenericTextEditor.__init__

        def latex_init(editor: LatexEditor, *args, **kwargs) -> None:
            original_latex_init(editor, *args, **kwargs)
            cls._attach_latex_features(editor)

        def yaml_init(editor: YamlEditor, *args, **kwargs) -> None:
            original_yaml_init(editor, *args, **kwargs)
            cls._attach_source_line_numbers(editor)

        def generic_init(editor: GenericTextEditor, *args, **kwargs) -> None:
            original_generic_init(editor, *args, **kwargs)
            cls._attach_source_line_numbers(editor)

        LatexEditor.__init__ = latex_init
        YamlEditor.__init__ = yaml_init
        GenericTextEditor.__init__ = generic_init

        # Existing non-bookmark startup integrations remain centralized here.
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
        WorkspaceReferenceController.install()
        cls._installed = True

    @staticmethod
    def _hide_legacy_bookmark_gutters(editor: LatexEditor) -> None:
        """Hide UI gutters that belonged to the retired line-bookmark model."""
        for name in ("_source_bookmark_gutter", "_visual_bookmark_gutter"):
            gutter = getattr(editor, name, None)
            if gutter is None:
                continue
            gutter.hide()
            gutter.setFixedWidth(0)

    @staticmethod
    def _apply_content_padding(editor: LatexEditor) -> None:
        """Use normal editor padding now that no bookmark gutter reserves width."""
        app_settings = editor._app_settings
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
    def _attach_latex_features(editor: LatexEditor) -> None:
        """Attach carets and Source line numbers without touching bookmarks."""
        editor._nd_source_persistent_caret = PersistentCaretOverlay(editor)
        editor._nd_visual_persistent_caret = PersistentCaretOverlay(
            editor._visual_editor
        )
        PersistentEditorVisuals._attach_source_line_numbers(editor)
        PersistentEditorVisuals._hide_legacy_bookmark_gutters(editor)
        PersistentEditorVisuals._apply_content_padding(editor)

    @staticmethod
    def _attach_source_line_numbers(editor) -> None:
        """Attach one gutter that numbers QTextDocument blocks, not soft wraps."""
        if getattr(editor, "_nd_logical_line_numbers", None) is not None:
            return
        editor._nd_logical_line_numbers = LogicalLineNumberOverlay(editor)
