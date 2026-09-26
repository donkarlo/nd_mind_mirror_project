from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_caret_freezes_visible_after_focus_leaves_editor() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/editor/cursor/"
        "cursor_appearance_controller.py"
    )

    focus_out = source.split(
        "elif event_type == QEvent.Type.FocusOut:", 1
    )[1].split(
        "elif event_type == QEvent.Type.Show:", 1
    )[0]
    restart = source.split(
        "def _restart_blink", 1
    )[1].split(
        "def _freeze_caret", 1
    )[0]
    freeze = source.split(
        "def _freeze_caret", 1
    )[1].split(
        "def _toggle_blink", 1
    )[0]

    assert "self._freeze_caret()" in focus_out
    assert "or not editor.hasFocus()" in restart
    assert "self._blink_timer.stop()" in freeze
    assert "self._blink_visible = True" in freeze
    assert "self._refresh()" in freeze


def test_source_and_visual_share_cursor_appearance_controller() -> None:
    visual = _read(
        "src/nd_mind_mirror/ui/editor/latex/"
        "latex_visual_editor.py"
    )
    latex_core = _read(
        "src/nd_mind_mirror/ui/editor/latex/core/"
        "latex_editor_core.py"
    )

    assert "CursorAppearanceController" in visual
    assert "self._cursor_appearance = CursorAppearanceController(self)" in visual
    assert "def apply_cursor_preferences(" in visual
    assert "super().apply_cursor_preferences(" in latex_core
    assert "visual_editor.apply_cursor_preferences(" in latex_core


def test_legacy_nonfocus_caret_renderers_are_not_active() -> None:
    rich_core = _read(
        "src/nd_mind_mirror/ui/editor/base/text_editor_rich_core.py"
    )
    startup_visuals = _read(
        "src/nd_mind_mirror/ui/window/main/"
        "persistent_editor_visuals.py"
    )

    assert "if not self.hasFocus():" not in rich_core
    assert "def focusOutEvent" not in rich_core
    assert "PersistentCaretOverlay" not in startup_visuals


def test_only_editor_pane_stretches_with_outer_window_width() -> None:
    controller = _read(
        "src/nd_mind_mirror/ui/window/main/"
        "main_panel_layout_controller.py"
    )
    enhanced_window = _read(
        "src/nd_mind_mirror/ui/window/main/"
        "enhanced_main_window_base.py"
    )

    assert "setStretchFactor(self._NAVIGATOR_INDEX, 0)" in controller
    assert "setStretchFactor(self._EDITOR_INDEX, 1)" in controller
    assert "setStretchFactor(self._PREVIEW_INDEX, 0)" in controller
    assert "MainPanelLayoutController" in enhanced_window
