from pathlib import Path

from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)
from nd_mind_mirror.ui.editor.latex.visual_source_window import VisualSourceWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _evil_sized_document() -> tuple[str, str, str, str]:
    prefix = "\\documentclass{article}\n\\begin{document}\n"
    line = "Persian prose text long enough to reproduce the evil document latency.\n"
    body = line * 4_700
    suffix = "\\end{document}\n"
    full_source = prefix + body + suffix
    assert 300_000 <= len(full_source) < 400_000
    return full_source, prefix, body, suffix


def test_evil_sized_source_uses_configured_large_editor_threshold() -> None:
    panel = _source("src/nd_mind_mirror/ui/panel/editor/editor_panel.py")
    large_editor = _source(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    )

    assert "editor_source_large_document_threshold_chars" in panel
    assert "if len(content) >= large_document_threshold" in panel
    assert "editor_source_large_document_threshold_chars" in large_editor
    assert "editor_source_virtualization_threshold_chars" not in large_editor
    assert "_DEFAULT_VIRTUALIZATION_THRESHOLD_CHARS" not in large_editor


def test_evil_sized_source_materializes_only_a_bounded_window() -> None:
    full_source, _prefix, _body, _suffix = _evil_sized_document()
    buffer = LatexSourceBuffer(threshold_chars=120_000, window_chars=40_000)
    buffer.set_source(full_source, focus_position=len(full_source) // 2)

    assert buffer.is_windowed is True
    assert len(buffer.window_text) < len(full_source) // 2
    assert buffer.source == full_source


def test_evil_sized_visual_projection_stays_bounded() -> None:
    full_source, prefix, body, suffix = _evil_sized_document()
    window = VisualSourceWindow()
    window.configure(
        threshold_chars=120_000,
        pages_above=2,
        pages_below=2,
        estimated_chars_per_page=2_400,
        min_lines_per_page=12,
        max_lines_per_page=45,
        max_window_chars=40_000,
    )

    projected = window.select(
        full_source=full_source,
        prefix=prefix,
        body=body,
        suffix=suffix,
        focus_line=2_300,
    )

    assert window.virtualized is True
    assert len(projected) <= 40_000
    assert window.splice(projected) == full_source


def test_visual_typing_updates_canonical_buffer_incrementally() -> None:
    source = _source(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    )
    method = source.split("def _apply_visual_source", 1)[1].split(
        "def _schedule_canonical_content_emit", 1
    )[0]

    assert "super()._apply_visual_source(source)" not in method
    assert "replace_source_incrementally(" in method
    assert "replace_source(canonical_source)" not in method
    assert "_source_materialization_stale = True" in method
    assert "_load_complete_source" not in method
    assert "_load_visible_window" not in method
    assert "_schedule_canonical_content_emit()" in method


def test_incremental_visual_replacement_preserves_untouched_chunks() -> None:
    full_source, _prefix, _body, _suffix = _evil_sized_document()
    buffer = LatexSourceBuffer(threshold_chars=120_000, window_chars=40_000)
    buffer.set_source(full_source, focus_position=len(full_source) // 2)
    old_chunks = buffer.snapshot_pieces()

    marker = "Persian prose text"
    edit_position = full_source.find(marker, len(full_source) // 2)
    assert edit_position > 0
    updated = (
        full_source[:edit_position]
        + "Edited Persian prose text"
        + full_source[edit_position + len(marker):]
    )

    assert buffer.replace_source_incrementally(updated) is True
    new_chunks = buffer.snapshot_pieces()

    assert buffer.source == updated
    assert buffer.is_windowed is True
    assert old_chunks[0] is new_chunks[0]
    assert old_chunks[-1] is new_chunks[-1]


def test_source_is_materialized_only_when_leaving_visual_mode() -> None:
    source = _source(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    )
    method = source.split("def set_edit_mode", 1)[1].split(
        "def apply_structural_source", 1
    )[0]

    assert "flush_pending_source_change()" in method
    assert "_source_materialization_stale" in method
    assert "_load_visible_window" in method
    assert "_load_complete_source" in method
