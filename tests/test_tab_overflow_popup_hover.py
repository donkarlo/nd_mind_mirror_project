"""Regression checks for removing explicit overflow-arrow widgets."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE = (
    ROOT / "src/nd_mind_mirror/ui/window/main/stable_pinned_tab_controller.py"
).read_text(encoding="utf-8")
BAR = (
    ROOT / "src/nd_mind_mirror/ui/switcher/hover_proxy_tab_bar.py"
).read_text(encoding="utf-8")


def test_no_explicit_overflow_button_is_created() -> None:
    assert "TabOverflowButton" not in STABLE
    assert "overflow_button" not in STABLE
    assert 'setText("▼")' not in STABLE


def test_native_scroll_buttons_remain_disabled() -> None:
    assert "bar.setUsesScrollButtons(False)" in STABLE


def test_proxy_tab_bar_has_no_overflow_activation_api() -> None:
    assert "activate_tab_from_overflow" not in BAR
