from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_visual_persian_core_no_longer_depends_on_legacy_caret_overlay() -> None:
    source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/visual_persian_font_core.py"
    ).read_text(encoding="utf-8")

    assert "persistent_caret_overlay" not in source
    assert "PersistentCaretOverlay" not in source
    assert "CursorAppearanceController" in source


def test_visual_caret_uses_the_shared_cursor_appearance_controller() -> None:
    source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/visual_persian_font_core.py"
    ).read_text(encoding="utf-8")

    assert "self._caret_controllers" in source
    assert "CursorAppearanceController(visual)" in source
    assert "controller.apply(" in source
