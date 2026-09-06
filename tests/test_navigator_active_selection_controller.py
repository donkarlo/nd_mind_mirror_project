"""Regression tests for active-editor selection synchronization in Navigator."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_active_selection_controller.py"
).read_text(encoding="utf-8")
WINDOW = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
).read_text(encoding="utf-8")


def test_active_document_forces_navigator_reveal() -> None:
    """Keep the visible Navigator row aligned with the selected editor tab."""
    assert "current_document_changed.connect" in CONTROLLER
    assert "select_path(path, force_reveal=True)" in CONTROLLER


def test_enhanced_window_owns_active_selection_controller() -> None:
    """Install the synchronization controller for the real application window."""
    assert "NavigatorActiveSelectionController(" in WINDOW
    assert "self._navigator_active_selection_controller" in WINDOW
