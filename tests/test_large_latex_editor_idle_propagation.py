from pathlib import Path


def _large_editor_source() -> str:
    project_root = Path(__file__).resolve().parents[1]
    path = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "editor"
        / "latex"
        / "large"
        / "large_latex_editor.py"
    )
    return path.read_text(encoding="utf-8")


def test_large_source_uses_bounded_qtextedit_window() -> None:
    source = _large_editor_source()
    assert "_DEFAULT_SOURCE_WINDOW_CHARS = 40_000" in source
    assert "LatexSourceBuffer(threshold, window_chars)" in source


def test_large_source_full_document_consumers_wait_for_idle() -> None:
    source = _large_editor_source()
    assert "_FULL_DOCUMENT_IDLE_MS = 1_200" in source
    assert "def _emit_content(self)" in source
    assert "self._content_emit_timer.setInterval(interval)" in source
    assert "def _schedule_bookmark_relocation(self)" in source
    assert "self._bookmark_relocation_timer.setInterval(" in source


def test_large_source_does_not_use_visible_document_size_for_debounce() -> None:
    source = _large_editor_source()
    method = source.split("def _emit_content(self)", 1)[1].split(
        "def _schedule_bookmark_relocation", 1
    )[0]
    assert "self.document().characterCount()" not in method
    assert "self.source_is_windowed" in method
