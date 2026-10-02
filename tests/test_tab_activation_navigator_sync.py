from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nd_mind_mirror"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_tab_activation_reuses_existing_navigator_reveal_behavior() -> None:
    panel = _read("ui/panel/editor/editor_panel_core.py")
    window = _read("ui/window/main/main_window.py")

    assert "active_tab_clicked = Signal(str)" in panel
    assert "active_tab_activated = Signal(str)" in panel
    assert "self.active_tab_activated.emit(str(path))" in panel
    assert "self._editor_panel.active_tab_clicked.connect(" in window
    assert "self._editor_panel.active_tab_activated.connect(" in window
    assert window.count("self._reveal_active_editor_tab") >= 2
    assert "force_reveal=True" in window
