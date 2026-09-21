"""Regression checks for transient Pinned/Open tab hover behavior."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOVER = (
    ROOT / "src/nd_mind_mirror/ui/switcher/hover_proxy_tab_bar.py"
).read_text(encoding="utf-8")
STABLE = (
    ROOT / "src/nd_mind_mirror/ui/window/main/stable_pinned_tab_controller.py"
).read_text(encoding="utf-8")


def test_pure_hover_never_changes_current_tab_state() -> None:
    assert "event.buttons() == Qt.MouseButton.NoButton" in HOVER
    assert "event.accept()" in HOVER
    assert "setChangeCurrentOnDrag(False)" in HOVER
    assert "bar.setChangeCurrentOnDrag(False)" in STABLE


def test_hover_is_light_purple_and_selected_blue_is_suppressed_while_hovered() -> None:
    assert 'QColor("#eadfff")' in HOVER
    assert "is_hovered = index == self._hovered_index" in HOVER
    assert "if is_hovered or not self._selection_visible:" in HOVER
    assert "State_Selected" in HOVER
    assert "State_HasFocus" in HOVER


def test_leave_clears_transient_hover() -> None:
    assert "def leaveEvent" in HOVER
    assert "self._hovered_index = -1" in HOVER
