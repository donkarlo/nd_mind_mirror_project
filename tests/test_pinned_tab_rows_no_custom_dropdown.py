"""Regression check that Pinned/Open rows have no custom file-list dropdown."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/stable_pinned_tab_controller.py"
).read_text(encoding="utf-8")


def test_stable_pinned_rows_do_not_add_a_custom_dropdown() -> None:
    assert "PinnedTabController" in STABLE
    assert "TabOverflowMenuButton" not in STABLE
    assert "NativeTabScrollerSuppressor" not in STABLE
    assert "_make_row" not in STABLE
