"""Regression check for large-editor cooperative initialization."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
).read_text(encoding="utf-8")
LARGE_CORE = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor_incremental_core.py"
).read_text(encoding="utf-8")


def test_force_visible_plain_text_exists_before_large_init_calls_super() -> None:
    assert "_force_visible_plain_text = False" in PUBLIC
    assert 'self._force_visible_plain_text or not hasattr(self, "_source_buffer")' in LARGE_CORE
