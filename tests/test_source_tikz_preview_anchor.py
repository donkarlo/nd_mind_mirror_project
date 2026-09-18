from nd_mind_mirror.ui.editor.latex.source_tikz_preview_anchor import (
    SourceTikZPreviewAnchor,
)


def test_preview_anchor_uses_end_of_include_line():
    source = "prefix\n" + r"\include{my_tikz.tex}" + "\nnext"
    start = source.index(r"\include")
    end = source.index("\nnext")
    assert SourceTikZPreviewAnchor.position(start, end) == end - 1


def test_preview_anchor_never_precedes_match_start():
    assert SourceTikZPreviewAnchor.position(8, 8) == 8
