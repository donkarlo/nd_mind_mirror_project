from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_preview_can_be_suspended_and_reopened():
    main = (ROOT / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text()
    panel = (ROOT / "src/nd_mind_mirror/ui/panel/preview/preview_panel.py").read_text()
    renderer = (ROOT / "src/nd_mind_mirror/core/render/latex/latex_renderer.py").read_text()
    assert 'QAction("Show Preview"' in main
    assert "close_requested = Signal()" in panel
    assert "def set_enabled(self, enabled: bool)" in renderer
    assert "if not self._preview_enabled:" in main


def test_graphic_bridge_auto_starts_with_application():
    main = (ROOT / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text()
    manager = (ROOT / "src/nd_mind_mirror/graphic/core/bridge_process_manager.py").read_text()
    defaults = (ROOT / "src/nd_mind_mirror/core/settings/defaults/settings.yaml").read_text()
    assert "GraphicBridgeProcessManager" in main
    assert "start_if_needed" in main
    assert "auto_start_bridge: true" in defaults
    assert '"-m", "nd_mind_mirror.graphic.bridge"' in manager


def test_navigator_delete_has_a_real_shortcut():
    source = (ROOT / "src/nd_mind_mirror/ui/panel/file_system/file_system_panel.py").read_text()
    assert 'QShortcut(QKeySequence("Delete"), self._tree)' in source
    assert "def _delete_selected_path" in source


def test_source_updates_are_coalesced():
    defaults = (ROOT / "src/nd_mind_mirror/core/settings/defaults/settings.yaml").read_text()
    latex = (ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py").read_text()
    generic = (ROOT / "src/nd_mind_mirror/ui/editor/generic/generic_text_editor.py").read_text()
    yaml = (ROOT / "src/nd_mind_mirror/ui/editor/yaml/yaml_editor.py").read_text()
    assert "source_update_debounce_ms: 70" in defaults
    for source in (latex, generic, yaml):
        assert "_content_emit_timer" in source
        assert "_flush_content" in source


def test_ipad_marker_and_eraser_use_segmented_tool_picker():
    content = (ROOT / "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/ContentView.swift").read_text()
    assert 'Picker("Tool", selection: $tool)' in content
    assert "GraphicTool.highlighter" in content
    assert "GraphicTool.eraser" in content
    assert ".pickerStyle(.segmented)" in content


def test_bookmarks_are_line_based_for_reliable_gutter_clicks():
    source = (ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py").read_text()
    assert "def _visual_bookmark_location_at_y" in source
    assert "del column" in source
    assert "column = 1" in source
