from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_large_source_keystrokes_do_not_splice_complete_source_string():
    source_buffer = _text(
        "src/nd_mind_mirror/core/document/latex/large/latex_source_buffer.py"
    )

    assert "self._chunks[first:last] = new_chunks" in source_buffer
    assert "self._materialized_source = None" in source_buffer
    assert "self._source[:old_start]" not in source_buffer
    assert "+ replacement\n            + self._source[old_end:]" not in source_buffer


def test_source_graphic_scroll_uses_visible_window_for_large_documents():
    controller = _text(
        "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
    )

    assert "def refresh_positions" in controller
    assert "_visible_plain_text_scope" in controller
    assert "super().refresh_positions()" in controller


def test_autosave_uses_chunk_snapshots_and_background_atomic_write():
    editor_panel = _text("src/nd_mind_mirror/ui/panel/editor/editor_panel.py")
    autosave = _text(
        "src/nd_mind_mirror/ui/window/main/autosave/document_autosave_controller.py"
    )
    window = _text("src/nd_mind_mirror/ui/window/main/enhanced_main_window.py")

    assert "autosave_snapshots" in editor_panel
    assert "autosave_revision_matches" in editor_panel
    assert "ThreadPoolExecutor" in autosave
    assert "for piece in pieces" in autosave
    assert "os.replace(temporary, path)" in autosave
    assert "DocumentAutosaveController" in window
    assert "controller.save_modified()" in window
    assert "controller.has_pending_writes" in window


def test_structure_remains_full_document_and_async_for_large_sources():
    structure_panel = _text(
        "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    )

    assert "LatexStructureParseWorker" in structure_panel
    assert "self._source" in structure_panel
