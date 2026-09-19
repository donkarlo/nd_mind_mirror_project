"""Source typing must not materialize the full canonical document per keystroke."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
MIXIN = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/bookmark/range/range_bookmark_editor_mixin.py"
).read_text(encoding="utf-8")
SELECTION_MIXIN = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/bookmark/range/selection_range_bookmark_editor_mixin.py"
).read_text(encoding="utf-8")
HIGHLIGHTER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/bookmark/range/range_bookmark_highlighter.py"
).read_text(encoding="utf-8")


def test_large_source_document_change_uses_incremental_tracker_api() -> None:
    body = MIXIN.split(
        "    def _synchronize_visible_change", 1
    )[1].split(
        "    def _on_range_bookmark_document_change", 1
    )[0]
    assert "tracker.apply_source_edit(" in body
    assert "tracker.apply_edit(" not in body
    assert "self.toPlainText()" not in body


def test_regular_source_document_change_uses_incremental_tracker_api() -> None:
    body = MIXIN.split(
        "    def _on_range_bookmark_document_change", 1
    )[1].split(
        "    def _range_bookmark_inserted_text", 1
    )[0]
    assert "tracker.apply_source_edit(" in body
    assert "self.toPlainText()" not in body


def test_bookmark_highlighter_does_not_refresh_both_views_together() -> None:
    refresh = HIGHLIGHTER.split(
        "    def refresh(self)", 1
    )[1].split(
        "    def refresh_source", 1
    )[0]
    assert "refresh_visual()" in refresh
    assert "refresh_source()" in refresh
    assert "_apply_source(" not in refresh
    assert "_apply_visual(" not in refresh


def test_selection_highlighter_adds_no_per_cursor_signal_connections() -> None:
    install = SELECTION_MIXIN.split(
        "    def _install_selection_highlighter", 1
    )[1].split(
        "    @staticmethod", 1
    )[0]
    assert "cursorPositionChanged" not in install
    assert ".connect(" not in install
