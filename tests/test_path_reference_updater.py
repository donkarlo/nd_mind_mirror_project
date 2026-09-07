from pathlib import Path

from nd_mind_mirror.core.workspace.path.path_reference_updater import (
    PathReferenceUpdater,
)


def test_rewrites_three_reference_path_modes_but_not_plain_text(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()

    old_file = assets / "old_name.pdf"
    new_file = assets / "new_name.pdf"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    source_file = docs / "main.tex"
    source_file.write_text(
        "\\includepdf{../assets/old_name.pdf}\n"
        "\\includegraphics{/assets/old_name.pdf}\n"
        f"\\includepdf{{{old_file}}}\n"
        "Plain prose: ../assets/old_name.pdf\n"
        "Plain prose: /assets/old_name.pdf\n"
        f"Plain prose: {old_file}\n",
        encoding="utf-8",
    )

    changed = PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    assert source_file.resolve() in changed
    source = source_file.read_text(encoding="utf-8")
    assert "\\includepdf{../assets/new_name.pdf}" in source
    assert "\\includegraphics{/assets/new_name.pdf}" in source
    assert f"\\includepdf{{{new_file}}}" in source
    assert "Plain prose: ../assets/old_name.pdf" in source
    assert "Plain prose: /assets/old_name.pdf" in source
    assert f"Plain prose: {old_file}" in source


def test_does_not_treat_plain_relative_token_as_default_rooted(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()

    old_file = assets / "old.png"
    new_file = assets / "new.png"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")
    source_file = docs / "main.tex"
    source_file.write_text(
        "\\includegraphics{assets/old.png}\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    assert source_file.read_text(encoding="utf-8") == (
        "\\includegraphics{assets/old.png}\n"
    )


def test_rewrites_extensionless_input_relative_to_referring_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    parts = workspace / "parts"
    docs.mkdir(parents=True)
    parts.mkdir()

    old_file = parts / "old_section.tex"
    new_file = parts / "new_section.tex"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")

    source_file = docs / "main.tex"
    source_file.write_text(
        "\\input{../parts/old_section}\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    assert source_file.read_text(encoding="utf-8") == (
        "\\input{../parts/new_section}\n"
    )


def test_rewrites_directory_prefix_only_inside_reference(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    old_dir = workspace / "figures" / "draft"
    new_dir = workspace / "figures" / "final"
    old_dir.mkdir(parents=True)
    new_dir.mkdir(parents=True)

    source_file = workspace / "paper.tex"
    source_file.write_text(
        "\\includegraphics{figures/draft/chart.png}\n"
        "The archive path is figures/draft/chart.png.\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_dir,
        new_dir,
    )

    source = source_file.read_text(encoding="utf-8")
    assert "\\includegraphics{figures/final/chart.png}" in source
    assert "The archive path is figures/draft/chart.png." in source


def test_respects_search_ignore_yaml_for_reference_scan(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    ignored_dir = workspace / "ignored"
    ignored_dir.mkdir(parents=True)
    assets = workspace / "assets"
    assets.mkdir()

    old_file = assets / "before.png"
    new_file = assets / "after.png"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    active = workspace / "active.tex"
    ignored = ignored_dir / "skip.tex"
    active.write_text(
        "\\includegraphics{/assets/before.png}\n",
        encoding="utf-8",
    )
    ignored.write_text(
        "\\includegraphics{/assets/before.png}\n",
        encoding="utf-8",
    )

    ignore_yaml = workspace / "search_ignore.yaml"
    ignore_yaml.write_text(
        "ignore:\n  - ignored/\n",
        encoding="utf-8",
    )

    changed = PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
        ignore_file_path=ignore_yaml,
    )

    assert active.resolve() in changed
    assert ignored.resolve() not in changed
    assert "/assets/after.png" in active.read_text(encoding="utf-8")
    assert "/assets/before.png" in ignored.read_text(encoding="utf-8")


def test_rewrites_comma_separated_bibliography_references(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    bib = workspace / "bib"
    bib.mkdir(parents=True)
    old_file = bib / "old.bib"
    new_file = bib / "new.bib"
    old_file.write_text("", encoding="utf-8")
    new_file.write_text("", encoding="utf-8")
    source_file = workspace / "main.tex"
    source_file.write_text(
        "\\bibliography{/bib/old,/bib/other}\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    assert source_file.read_text(encoding="utf-8") == (
        "\\bibliography{/bib/new,/bib/other}\n"
    )
