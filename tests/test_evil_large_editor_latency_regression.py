from pathlib import Path

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

    assert "editor_source_large_document_threshold_chars" in panel
    assert "if len(content) >= large_document_threshold" in panel
    assert "_SOURCE_VIRTUALIZATION_THRESHOLD_CHARS = 1_000_000" not in panel


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


def test_visual_typing_does_not_rewrite_hidden_source_document() -> None:
    source = _source(
        "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    )
    method = source.split("def _apply_visual_source", 1)[1].split(
        "def _schedule_canonical_content_emit", 1
    )[0]

    assert "super()._apply_visual_source(source)" not in method
    assert "_source_materialization_stale = True" in method
    assert "_load_complete_source" not in method
    assert "_load_visible_window" not in method
    assert "_schedule_canonical_content_emit()" in method


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
