"""Regression tests for the canonical three workspace reference path modes."""

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


def test_relative_path_is_only_relative_to_referring_file(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    docs = workspace / "docs"
    docs_assets = docs / "assets"
    root_assets = workspace / "assets"
    docs_assets.mkdir(parents=True)
    root_assets.mkdir()
    local_target = docs_assets / "figure.png"
    root_target = root_assets / "figure.png"
    local_target.write_bytes(b"local")
    root_target.write_bytes(b"root")
    referring_file = docs / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(workspace)

    assert resolver.resolve(
        "assets/figure.png",
        referring_file,
        command="includegraphics",
    ) == local_target.resolve()
    assert resolver.candidate_paths(
        "assets/figure.png",
        referring_file,
    ) == [("file_relative", local_target.resolve())]


def test_leading_slash_prefers_default_path_then_system_absolute(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()
    default_target = assets / "figure.png"
    default_target.write_bytes(b"default")
    referring_file = docs / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(workspace)

    assert resolver.resolve(
        "/assets/figure.png",
        referring_file,
        command="includegraphics",
    ) == default_target.resolve()

    absolute_target = tmp_path / "outside.pdf"
    absolute_target.write_bytes(b"pdf")
    assert resolver.resolve(
        absolute_target.as_posix(),
        referring_file,
        command="includepdf",
    ) == absolute_target.resolve()


def test_repo_prefix_has_no_special_alias_semantics(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    project = workspace / "project"
    project.mkdir(parents=True)
    referring_file = project / "main.tex"
    referring_file.write_text("", encoding="utf-8")

    resolver = WorkspaceReferenceResolver(workspace)
    candidates = resolver.candidate_paths(
        "/repo/project/file.tex",
        referring_file,
    )

    assert [kind for kind, _path in candidates] == [
        "default_rooted",
        "absolute",
    ]
    assert candidates[0][1] == (
        workspace / "repo" / "project" / "file.tex"
    ).resolve()
    assert all(kind != "repository_alias" for kind, _path in candidates)


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


def test_delete_removes_only_matching_default_rooted_bibliography_item(
    tmp_path: Path,
) -> None:
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
    updated = resolver.remove_references(
        source,
        referring_file,
        old_file,
    )

    assert updated == "\\bibliography{/bib/keep}\n"


def test_ctrl_b_occurrence_resolution_uses_same_policy_for_supported_resources(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    project = workspace / "project"
    images = workspace / "images"
    pdfs = workspace / "pdfs"
    bib = workspace / "bib"
    project.mkdir(parents=True)
    images.mkdir()
    pdfs.mkdir()
    bib.mkdir()

    image = images / "figure.png"
    pdf = pdfs / "paper.pdf"
    bibliography = bib / "refs.bib"
    source_file = project / "source.tex"
    for path in (image, pdf, bibliography, source_file):
        path.write_bytes(b"x")

    referring_file = project / "main.tex"
    source = (
        "\\href{source.tex}{source}\n"
        "\\includegraphics{/images/figure.png}\n"
        "\\includepdf{/pdfs/paper.pdf}\n"
        "\\bibliography{/bib/refs}\n"
    )
    resolver = WorkspaceReferenceResolver(workspace)

    expectations = {
        "source.tex": source_file.resolve(),
        "/images/figure.png": image.resolve(),
        "/pdfs/paper.pdf": pdf.resolve(),
        "/bib/refs": bibliography.resolve(),
    }
    for token, expected in expectations.items():
        offset = source.index(token) + 1
        occurrence = resolver.occurrence_at(
            source,
            referring_file,
            offset,
        )
        assert occurrence is not None
        assert occurrence.target_path == expected


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
