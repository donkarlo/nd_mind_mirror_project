"""Regression checks for per-row mouseout restoration in tab overflow popups."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/switcher/tab_overflow_popup_hover_controller.py"
).read_text(encoding="utf-8")
DELEGATE = (
    ROOT
    / "src/nd_mind_mirror/ui/switcher/single_hover_item_delegate.py"
).read_text(encoding="utf-8")


def test_mouse_move_uses_index_at_and_repaints_old_and_new_rows() -> None:
    assert "view.indexAt(point)" in CONTROLLER
    assert "previous = delegate.hovered_index" in CONTROLLER
    assert "view.viewport().update(view.visualRect(previous))" in CONTROLLER
    assert "view.viewport().update(view.visualRect(current))" in CONTROLLER


def test_mouseout_clears_hover_immediately() -> None:
    assert "QEvent.Type.Leave" in CONTROLLER
    assert "QEvent.Type.HoverLeave" in CONTROLLER
    assert "self._set_view_hover(QModelIndex())" in CONTROLLER


def test_non_hovered_rows_are_explicitly_restored_to_normal_background() -> None:
    assert "else clean.palette.base()" in DELEGATE
    assert 'QColor("#eadfff")' in DELEGATE
    assert "State_Selected" in DELEGATE
    assert "State_MouseOver" in DELEGATE
