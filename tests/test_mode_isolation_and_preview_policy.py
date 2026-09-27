"""Regression coverage for strict editor-mode and Preview work isolation."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
LATEX_EDITOR = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/mode/mode_isolated_latex_editor.py"
).read_text(encoding="utf-8")
SOURCE_LATEX_CONTROLLER = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_latex_preview_controller.py"
).read_text(encoding="utf-8")
SOURCE_TIKZ_CONTROLLER = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_tikz_preview_controller.py"
).read_text(encoding="utf-8")
READABLE_SOURCE = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/readable_source_latex_preview_controller.py"
).read_text(encoding="utf-8")
SOURCE_GRAPHIC = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
).read_text(encoding="utf-8")
PREVIEW_POLICY = (
    ROOT / "src/nd_mind_mirror/ui/window/main/preview_render_policy_controller.py"
).read_text(encoding="utf-8")
ENHANCED_WINDOW = (
    ROOT / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")
LAUNCHER = (ROOT / "nd_mind_mirror_project").read_text(encoding="utf-8")
EDITOR_RUNTIME_EXTENSIONS = (
    ROOT / "src/nd_mind_mirror/ui/window/main/editor_runtime_extensions.py"
).read_text(encoding="utf-8")
RUNTIME_FIXES = (
    ROOT / "src/nd_mind_mirror/ui/window/main/runtime_fixes.py"
).read_text(encoding="utf-8")
SAFE_APPLICATION = (
    ROOT / "src/nd_mind_mirror/app/safe_mind_mirror_application.py"
).read_text(encoding="utf-8")

LOGICAL_LINE_NUMBERS = (
    ROOT / "src/nd_mind_mirror/ui/window/main/logical_line_number_overlay.py"
).read_text(encoding="utf-8")


def test_source_cursor_does_not_update_hidden_visual_cursor() -> None:
    source_handler = LATEX_EDITOR.split(
        "    def _on_source_cursor_changed", 1
    )[1].split("    def _on_visual_cursor_changed", 1)[0]
    assert "set_selection_from_source_locations" not in source_handler
    assert "active_cursor_changed.emit()" in source_handler


def test_visual_cursor_does_not_update_hidden_source_cursor() -> None:
    visual_handler = LATEX_EDITOR.split(
        "    def _on_visual_cursor_changed", 1
    )[1].split("    def _apply_visual_source", 1)[0]
    assert "_set_source_selection_from_locations" not in visual_handler
    assert "active_cursor_changed.emit()" in visual_handler


def test_visual_edits_use_cached_incremental_canonical_source() -> None:
    assert "self._visual_source_cache" in LATEX_EDITOR
    assert "_common_prefix_length" in LATEX_EDITOR
    assert "_common_suffix_length" in LATEX_EDITOR
    assert "self._formatter.format" not in LATEX_EDITOR
    assert "highlighter.setDocument(None)" in LATEX_EDITOR


def test_source_preview_controllers_gate_hidden_mode_work() -> None:
    assert 'editor.edit_mode != "source"' in SOURCE_LATEX_CONTROLLER
    assert 'editor.edit_mode != "source"' in SOURCE_TIKZ_CONTROLLER
    assert "_refresh_timer.stop()" in SOURCE_LATEX_CONTROLLER
    assert "_refresh_timer.stop()" in SOURCE_TIKZ_CONTROLLER


def test_formula_and_graphic_geometry_wait_for_qt_layout_settle() -> None:
    assert "_GEOMETRY_SETTLE_MS = 16" in READABLE_SOURCE
    assert "_geometry_settle_timer" in READABLE_SOURCE
    assert "_settle_layout_geometry" in READABLE_SOURCE
    assert "_GEOMETRY_SETTLE_MS = 16" in SOURCE_GRAPHIC
    assert "_geometry_settle_timer" in SOURCE_GRAPHIC


def test_source_graphic_polling_stops_outside_source_mode() -> None:
    assert "_sync_polling_state" in SOURCE_GRAPHIC
    assert "timer.stop()" in SOURCE_GRAPHIC
    assert "_source_is_active" in SOURCE_GRAPHIC


def test_closed_preview_does_no_validation_or_extra_render() -> None:
    assert "_preview_is_enabled" in PREVIEW_POLICY
    assert "first_missing_latex_input" in PREVIEW_POLICY
    assert "self._renderer.render(" not in PREVIEW_POLICY
    assert "def _on_renderer_dependencies_changed" in ENHANCED_WINDOW
    dependency_handler = ENHANCED_WINDOW.split(
        "    def _on_renderer_dependencies_changed", 1
    )[1].split("    def _sync_preview_dependency_changes", 1)[0]
    assert "_preview_enabled" in dependency_handler
    assert "self._preview_dependency_signatures = {}" in dependency_handler


def test_tikz_updates_touch_only_the_active_projection() -> None:
    live = ENHANCED_WINDOW.split(
        "    def _refresh_tikz_live_projections", 1
    )[1].split("    def _refresh_tikz_idle_projections", 1)[0]
    assert 'if mode == "source"' in live
    assert 'elif mode == "visual"' in live


def test_startup_does_not_install_runtime_monkey_patches() -> None:
    assert "SafeLargeDocumentPerformanceController" not in LAUNCHER
    assert "install_startup_hook" not in LAUNCHER


def test_startup_does_not_override_or_resurrect_range_bookmarks() -> None:
    assert "_install_selection_bookmarks" not in EDITOR_RUNTIME_EXTENSIONS
    assert "_install_bookmark_relocation" not in EDITOR_RUNTIME_EXTENSIONS
    assert "_patch_bookmark_gutter" not in RUNTIME_FIXES
    assert "_patch_bookmark_manager" not in RUNTIME_FIXES
    assert "_recover_lost_evil_bookmark" not in SAFE_APPLICATION


def test_hidden_source_suspends_line_numbers_and_bookmark_relocation() -> None:
    assert "line_numbers.set_active(False)" in LATEX_EDITOR
    assert "self._bookmark_relocation_timer.stop()" in LATEX_EDITOR
    bookmark_schedule = LATEX_EDITOR.split(
        "    def _schedule_bookmark_relocation", 1
    )[1].split("    def _on_source_cursor_changed", 1)[0]
    assert '!= "source"' in bookmark_schedule
    assert "super()._schedule_bookmark_relocation()" in bookmark_schedule
    assert "def set_active(self, active: bool)" in LOGICAL_LINE_NUMBERS
    assert "self._disconnect_updates()" in LOGICAL_LINE_NUMBERS
    assert "self._editor.textChanged.disconnect(self._refresh)" in LOGICAL_LINE_NUMBERS
