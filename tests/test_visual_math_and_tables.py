"""Regression coverage for Visual math previews and editable LaTeX tables."""

from nd_mind_mirror.ui.editor.latex.visual.table.latex_table_parser import (
    LatexTableParser,
)


def test_tabular_round_trip_preserves_wrapper_and_supports_new_grid_cells() -> None:
    source = r"""\begin{table}[H]
\centering
\caption{Demo}
\begin{tabular}{|l|c|}
A & B \\
C & D \\
\end{tabular}
\end{table}"""
    model = LatexTableParser().parse(source, source_line=12)
    assert model is not None
    model.insert_row(1)
    model.insert_column(1)
    serialized = model.serialize()
    assert r"\begin{table}[H]" in serialized
    assert r"\caption{Demo}" in serialized
    assert r"\begin{tabular}{|l|l|c|}" in serialized
    assert len(model.rows) == 3
    assert all(len(row) == 3 for row in model.rows)


def test_advanced_merged_cells_remain_raw_instead_of_being_rewritten() -> None:
    source = r"""\begin{tabular}{lc}
\multicolumn{2}{c}{Title} \\
A & B \\
\end{tabular}"""
    assert LatexTableParser().parse(source) is None
