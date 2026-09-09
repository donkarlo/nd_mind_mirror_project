"""Regression tests for workspace-rooted structural paths in LaTeX Preview."""

from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)


def test_preview_rewrites_default_rooted_preamble_input_to_filesystem_path(
    tmp_path: Path,
) -> None:
    default_root = tmp_path / "repo"
    presentation_dir = (
        default_root
        / "nd_research_publication"
        / "src"
        / "kind"
        / "presentation"
    )
    presentation_dir.mkdir(parents=True)

    target = (
        default_root
        / "nd_language_ai_project"
        / "src"
        / "nd_language_ai"
        / "formal"
        / "computer"
        / "programming"
        / "tex"
        / "latex"
        / "code_clips"
        / "external_graphviz.tex"
    )
    target.parent.mkdir(parents=True)
    target.write_text("\\newcommand{\\graphvizsentinel}{ok}\n", encoding="utf-8")

    master = presentation_dir / "presentation.tex"
    raw_target = (
        "/nd_language_ai_project/src/nd_language_ai/formal/computer/"
        "programming/tex/latex/code_clips/external_graphviz.tex"
    )
    source = (
        "\\documentclass{beamer}\n"
        f"\\input{{{raw_target}}}\n"
        "\\begin{document}\n"
        "\\begin{frame}Preview\\end{frame}\n"
        "\\end{document}\n"
    )
    master.write_text(source, encoding="utf-8")

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert f"\\input{{{raw_target}}}" not in rendered
    assert f"\\input{{{target.resolve().as_posix()}}}" in rendered
    assert not resolver.unresolved


def test_structural_preview_rewrite_preserves_file_relative_resolution(
    tmp_path: Path,
) -> None:
    default_root = tmp_path / "repo"
    presentation_dir = default_root / "project" / "presentation"
    presentation_dir.mkdir(parents=True)

    target = presentation_dir / "shared" / "macros.tex"
    target.parent.mkdir(parents=True)
    target.write_text("\\newcommand{\\sentinel}{ok}\n", encoding="utf-8")

    master = presentation_dir / "presentation.tex"
    source = (
        "\\documentclass{article}\n"
        "\\input{shared/macros.tex}\n"
        "\\begin{document}ok\\end{document}\n"
    )

    resolver = WorkspaceRecursiveInputResolver(default_root)
    rendered = resolver.resolve(source, master)

    assert f"\\input{{{target.resolve().as_posix()}}}" in rendered
    assert not resolver.unresolved
