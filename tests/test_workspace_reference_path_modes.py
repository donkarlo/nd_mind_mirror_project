"""Regression tests for the three workspace path-reference modes."""

from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)
from nd_mind_mirror.core.workspace.path.path_reference_updater import (
    PathReferenceUpdater,
)
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


def test_resolves_relative_default_rooted_and_system_absolute_paths(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()
    target = assets / "figure.png"
    target.write_bytes(b"png")
    referring_file = docs / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(workspace)

    assert resolver.resolve(
        "../assets/figure.png",
        referring_file,
        command="includegraphics",
    ) == target.resolve()
    assert resolver.resolve(
        "/assets/figure.png",
        referring_file,
        command="includegraphics",
    ) == target.resolve()
    assert resolver.resolve(
        target.as_posix(),
        referring_file,
        command="includegraphics",
    ) == target.resolve()


def test_move_preserves_all_three_path_styles(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()
    old_file = assets / "old.png"
    new_file = assets / "new.png"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")
    referring_file = docs / "main.tex"

    source = (
        "\\includegraphics{../assets/old.png}\n"
        "\\includegraphics{/assets/old.png}\n"
        f"\\includegraphics{{{old_file.as_posix()}}}\n"
    )
    updated = PathReferenceUpdater.rewrite_source_for_mappings(
        source,
        referring_file=referring_file,
        workspace_root=workspace,
        mappings=[(old_file, new_file)],
    )

    assert "\\includegraphics{../assets/new.png}" in updated
    assert "\\includegraphics{/assets/new.png}" in updated
    assert f"\\includegraphics{{{new_file.as_posix()}}}" in updated


def test_delete_removes_only_matching_bibliography_item(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    bib = workspace / "bib"
    bib.mkdir(parents=True)
    old_file = bib / "old.bib"
    keep_file = bib / "keep.bib"
    old_file.write_text("", encoding="utf-8")
    keep_file.write_text("", encoding="utf-8")
    referring_file = workspace / "main.tex"
    source = "\\bibliography{/bib/old,/bib/keep}\n"

    resolver = WorkspaceReferenceResolver(workspace)
    updated = resolver.remove_references(source, referring_file, old_file)

    assert updated == "\\bibliography{/bib/keep}\n"


def test_recursive_preview_resolves_default_rooted_input(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    publication = workspace / "nd_research_publication" / "parts"
    publication.mkdir(parents=True)
    child = publication / "child.tex"
    child.write_text("Child content.\n", encoding="utf-8")
    master = workspace / "paper" / "main.tex"
    master.parent.mkdir()
    source = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{/nd_research_publication/parts/child}\n"
        "\\end{document}\n"
    )

    resolver = WorkspaceRecursiveInputResolver(workspace)
    expanded = resolver.resolve(source, master)

    assert "Child content." in expanded
    assert resolver.unresolved == []
    assert child.resolve() in resolver.resolved_paths


def test_preview_rewrites_default_rooted_preamble_and_graphic_paths(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    bib = workspace / "bib"
    images = workspace / "images"
    bib.mkdir(parents=True)
    images.mkdir()
    bibliography = bib / "refs.bib"
    image = images / "figure.png"
    bibliography.write_text("", encoding="utf-8")
    image.write_bytes(b"png")
    master = workspace / "paper" / "main.tex"
    master.parent.mkdir()
    source = (
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{biblatex}\n"
        "\\addbibresource{/bib/refs.bib}\n"
        "\\begin{document}\n"
        "\\includegraphics{/images/figure.png}\n"
        "\\end{document}\n"
    )

    resolver = WorkspaceRecursiveInputResolver(workspace)
    expanded = resolver.resolve(source, master)

    assert bibliography.resolve().as_posix() in expanded
    assert image.resolve().as_posix() in expanded
