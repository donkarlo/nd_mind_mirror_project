from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_startup_large_document_chain_has_no_removed_visual_controller_reference():
    launcher = _text("nd_mind_mirror_project")
    startup_files = [
        _text(
            "src/nd_mind_mirror/ui/window/main/large_document_performance_controller.py"
        ),
        _text(
            "src/nd_mind_mirror/ui/window/main/safe_large_document_performance_controller.py"
        ),
        _text(
            "src/nd_mind_mirror/ui/window/main/editor_runtime_extensions.py"
        ),
        _text(
            "src/nd_mind_mirror/ui/window/main/persistent_editor_visuals.py"
        ),
    ]

    assert "SafeLargeDocumentPerformanceController" in launcher
    for source in startup_files:
        assert "visual_window_controller" not in source
        assert "VisualWindowController" not in source
    assert "_install_visual_virtualization_threshold" not in startup_files[0]
    assert "_install_visual_virtualization_threshold" not in startup_files[1]
    assert "_install_visual_window_settings" not in startup_files[2]
    assert "_install_large_document_visual_performance" not in startup_files[3]


def test_visual_windowing_is_owned_by_the_visual_editor_architecture():
    editor = _text("src/nd_mind_mirror/ui/editor/latex/latex_editor.py")
    windowed = _text(
        "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor.py"
    )
    structure = _text(
        "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    )

    assert "WindowedLatexVisualEditor" in editor
    assert "class WindowedLatexVisualEditor" in windowed
    assert "self._latex_parser.parse(self._source)" in structure

