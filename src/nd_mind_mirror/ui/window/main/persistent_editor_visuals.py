"""Install persistent editor visuals, logical line numbers, and shared source indentation."""

from __future__ import annotations

from collections.abc import Callable

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
        WorkspaceReferenceController.install()
        cls._installed = True

    @staticmethod
    def _attach_latex_features(editor: LatexEditor) -> None:
        """Attach persistent carets and one logical-line-number gutter to LaTeX Source."""
        editor._nd_source_persistent_caret = PersistentCaretOverlay(editor)
        editor._nd_visual_persistent_caret = PersistentCaretOverlay(editor._visual_editor)
        PersistentEditorVisuals._attach_source_line_numbers(editor)

    @staticmethod
    def _attach_source_line_numbers(editor) -> None:
        """Attach one gutter that numbers QTextDocument blocks, never soft-wrap rows."""
        if getattr(editor, "_nd_logical_line_numbers", None) is not None:
            return
        editor._nd_logical_line_numbers = LogicalLineNumberOverlay(editor)
