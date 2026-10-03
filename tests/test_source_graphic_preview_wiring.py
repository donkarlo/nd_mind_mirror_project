from pathlib import Path

ROOT = Path(__file__).parent.parent
MAIN_WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")
SOURCE_PREVIEW_CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
).read_text(encoding="utf-8")
PREVIEW_POLICY_CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/preview_render_policy_controller.py"
).read_text(encoding="utf-8")


def test_enhanced_window_owns_source_graphic_preview_controller_directly():
    assert "class EnhancedMainWindow(MainWindow):" in MAIN_WINDOW
    assert (
        "self._source_graphic_preview_controller = SourceGraphicPreviewController("
        in MAIN_WINDOW
    )
    assert "self._editor_panel" in MAIN_WINDOW


def test_enhanced_window_owns_preview_render_policy_without_runtime_patching():
    assert (
        "self._preview_render_policy_controller = PreviewRenderPolicyController("
        in MAIN_WINDOW
    )
    assert "_install_preview_render_recovery" not in MAIN_WINDOW
    assert "renderer.render =" not in MAIN_WINDOW
    assert "renderer._compile_pending_source =" not in MAIN_WINDOW


def test_preview_render_policy_uses_editor_signals_and_public_renderer_api():
    assert "class PreviewRenderPolicyController(QObject):" in PREVIEW_POLICY_CONTROLLER
    assert "current_document_changed.connect" in PREVIEW_POLICY_CONTROLLER
    assert "current_content_changed.connect" in PREVIEW_POLICY_CONTROLLER
    assert "self._renderer.render(" in PREVIEW_POLICY_CONTROLLER
    assert "immediate=True" in PREVIEW_POLICY_CONTROLLER
    assert "self._renderer.failed.emit" in PREVIEW_POLICY_CONTROLLER


def test_source_graphic_preview_wiring_has_no_wrapper_or_base_class_workaround():
    assert "BaseEnhancedMainWindow" not in MAIN_WINDOW
    assert "enhanced_main_window_base" not in MAIN_WINDOW


def test_existing_enhanced_window_features_are_preserved():
    assert "VisualWindowController" in MAIN_WINDOW
    assert "PreviewReverseSyncController" in MAIN_WINDOW
    assert "PreviewAutoFitController" in MAIN_WINDOW


def test_source_preview_controller_reacts_to_editor_state_changes():
    assert "current_document_changed.connect" in SOURCE_PREVIEW_CONTROLLER
    assert "current_content_changed.connect" in SOURCE_PREVIEW_CONTROLLER
    assert "current_view_changed.connect" in SOURCE_PREVIEW_CONTROLLER
    assert "QTimer.singleShot(0, self._rebuild_layout)" in SOURCE_PREVIEW_CONTROLLER


def test_source_preview_ignores_non_latex_editors_before_reading_edit_mode():
    assert "from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor" in SOURCE_PREVIEW_CONTROLLER
    assert (
        'if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":'
        in SOURCE_PREVIEW_CONTROLLER
    )
    assert 'if editor.edit_mode != "source":' not in SOURCE_PREVIEW_CONTROLLER
