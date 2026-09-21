from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_caret_blinks_while_visible_after_focus_leaves_editor() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/editor/cursor/"
        "cursor_appearance_controller.py"
    )

    restart = source.split(
        "def _restart_blink", 1
    )[1].split(
        "def _toggle_blink", 1
    )[0]
    refresh = source.split(
        "def _refresh", 1
    )[1]

    assert "if not self._editor.hasFocus()" not in restart
    assert "or not self._editor.hasFocus()" not in refresh
    assert "QEvent.Type.FocusOut" in source
    assert "self._restart_blink()" in source


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
