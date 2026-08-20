from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)


def test_resolved_paths_include_tikz_and_nested_input(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    figures = root / "figures"
    figures.mkdir()
    nested = figures / "nodes.tex"
    nested.write_text("\\node (a) at (0,0) {A};\n", encoding="utf-8")
    diagram = figures / "graph.tikz"
    diagram.write_text(
        "\\begin{tikzpicture}\n"
        "\\input{nodes}\n"
        "\\end{tikzpicture}\n",
        encoding="utf-8",
    )
    master = root / "main.tex"
    source = (
        "\\documentclass{article}\n"
        "\\usepackage{tikz}\n"
        "\\begin{document}\n"
        "\\input{figures/graph.tikz}\n"
        "\\end{document}\n"
    )
    master.write_text(source, encoding="utf-8")

    resolver = RecursiveInputResolver()
    resolver.resolve(source, master)

    assert diagram.resolve() in resolver.resolved_paths
    assert nested.resolve() in resolver.resolved_paths
