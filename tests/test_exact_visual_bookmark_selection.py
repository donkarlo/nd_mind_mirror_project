"""Regression check: a Visual bookmark never expands beyond selected words."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOLVER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/bookmark/range/range_bookmark_selection_resolver.py"
).read_text(encoding="utf-8")


def test_literal_visual_selection_precedes_structural_serializer() -> None:
    selected = RESOLVER.index("if selected_visual.strip():")
    serializer = RESOLVER.index('serializer = getattr(visual, "_selected_latex_source", None)')
    assert selected < serializer
    assert "bookmark must never widen" in RESOLVER
    assert "maximum_serialized_length" in RESOLVER
    assert "serialized_length <= maximum_serialized_length" in RESOLVER
