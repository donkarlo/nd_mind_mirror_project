"""Regression coverage for Source graphic-preview tab-switch anchoring."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
).read_text(encoding="utf-8")


def test_graphic_preview_detach_preserves_inactive_tab_vertical_anchor() -> None:
    """Preview-margin teardown must restore the top-visible source anchor."""
    method = CONTROLLER.split("    def _detach_editor", 1)[1].split(
        "    @staticmethod", 1
    )[0]

    assert "anchor = self._capture_vertical_anchor(editor)" in method
    assert "super()._detach_editor()" in method
    assert "self._restore_vertical_anchor(editor, anchor)" in method
    assert "QTimer.singleShot(" in method
    assert "self._restore_detached_vertical_anchor" in method


def test_deferred_anchor_restore_is_safe_for_destroyed_tabs() -> None:
    """Deferred geometry correction must tolerate a tab closing meanwhile."""
    method = CONTROLLER.split(
        "    def _restore_detached_vertical_anchor", 1
    )[1].split("    @staticmethod", 1)[0]

    assert "try:" in method
    assert "except RuntimeError:" in method
