from nd_mind_mirror.core.render.latex.latex_preview_cache_signal_bus import (
    LatexPreviewCacheSignalBus,
)
from nd_mind_mirror.core.render.latex.latex_renderer import LatexRenderer


def test_preview_cache_signals_are_not_declared_on_renderer_subclass() -> None:
    assert "cached_preview_available" not in LatexRenderer.__dict__
    assert "preview_source_empty" not in LatexRenderer.__dict__


def test_preview_cache_signals_have_a_dedicated_qobject_owner() -> None:
    assert "cached_preview_available" in LatexPreviewCacheSignalBus.__dict__
    assert "preview_source_empty" in LatexPreviewCacheSignalBus.__dict__
