from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_visual_projection_flushes_pending_edit_before_hide() -> None:
    source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor.py"
    ).read_text(encoding="utf-8")

    assert "def flush_pending_source_change" in source
    assert "if not self._emit_timer.isActive():" in source
    assert "self._emit_serialized_source()" in source
    assert "def hideEvent" in source
    assert "self.flush_pending_source_change()" in source


def test_moderate_latex_documents_do_not_use_chunked_source_editor() -> None:
    source = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/panel/editor/editor_panel.py"
    ).read_text(encoding="utf-8")

    assert "_SOURCE_VIRTUALIZATION_THRESHOLD_CHARS = 1_000_000" in source
    assert "if len(content) >= self._SOURCE_VIRTUALIZATION_THRESHOLD_CHARS" in source
    assert "else SelectionLatexEditor" in source
