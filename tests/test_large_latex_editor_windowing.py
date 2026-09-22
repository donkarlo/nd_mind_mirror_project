"""Regression checks for bounded large-LaTeX Source materialization."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTION_LARGE = (
    ROOT / "src/nd_mind_mirror/ui/editor/bookmark/selection_large_latex_editor.py"
).read_text(encoding="utf-8")
PUBLIC = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
).read_text(encoding="utf-8")


def test_large_editor_virtualizes_at_large_document_threshold() -> None:
    assert "_DEFAULT_VIRTUALIZATION_THRESHOLD_CHARS = 120_000" in SELECTION_LARGE
    assert "_force_visible_plain_text = False" in PUBLIC
