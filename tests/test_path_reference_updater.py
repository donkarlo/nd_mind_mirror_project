from pathlib import Path

from nd_mind_mirror.core.workspace.path.path_reference_updater import (
    PathReferenceUpdater,
)


def test_rewrites_absolute_workspace_and_relative_tex_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    old_dir = workspace / "parts" / "old"
    new_dir = workspace / "parts" / "new"
    old_dir.mkdir(parents=True)
    new_dir.mkdir(parents=True)

    old_file = old_dir / "language.tex"
    new_file = new_dir / "language.tex"
    main = workspace / "main.tex"
    main.write_text(
        "\\input{parts/old/language}\n"
        f"\\input{{{old_file}}}\n",
        encoding="utf-8",
    )

    changed = PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    assert main.resolve() in changed
    source = main.read_text(encoding="utf-8")
    assert "\\input{parts/new/language}" in source
    assert str(new_file) in source
    assert "parts/old/language" not in source


def test_rewrites_directory_prefixes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    old_dir = workspace / "figures" / "draft"
    new_dir = workspace / "figures" / "final"
    old_dir.mkdir(parents=True)
    new_dir.mkdir(parents=True)
    source_file = workspace / "paper.tex"
    source_file.write_text(
        "\\includegraphics{figures/draft/chart.png}\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_dir,
        new_dir,
    )

    assert "figures/final/chart.png" in source_file.read_text(encoding="utf-8")
