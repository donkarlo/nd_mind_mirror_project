from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)
from nd_mind_mirror.ui.window.main.image_sequence_fix import ImageSequenceFix


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


def test_preview_graphic_path_is_resolved_beside_containing_tex_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source_dir = root / "data" / "career" / "prompt" / "migration"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "migration.tex"
    source_path.write_text("", encoding="utf-8")

    expected_image = source_dir / "img_0.png"
    expected_image.write_bytes(b"correct")

    wrong_image = root / "data" / "career" / "img_0.png"
    wrong_image.parent.mkdir(parents=True, exist_ok=True)
    wrong_image.write_bytes(b"wrong")

    rewritten = ImageSequenceFix._rewrite_includegraphics_paths(
        r"\includegraphics[width=0.9\textwidth]{img_0.png}",
        source_path,
    )

    assert expected_image.resolve().as_posix() in rewritten
    assert wrong_image.resolve().as_posix() not in rewritten
