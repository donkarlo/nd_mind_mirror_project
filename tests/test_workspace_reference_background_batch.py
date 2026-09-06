"""Regression tests for batched reference updates used by background file operations."""

from pathlib import Path

from nd_mind_mirror.core.workspace.path.path_reference_updater import PathReferenceUpdater


def test_batch_move_updates_multiple_targets_in_one_source(tmp_path: Path) -> None:
    """Apply several move mappings without requiring a separate workspace pass per target."""
    repository_root = tmp_path / "repo"
    project = repository_root / "project"
    assets = project / "assets"
    docs = project / "docs"
    assets.mkdir(parents=True)
    docs.mkdir()

    old_image = assets / "old.png"
    new_image = assets / "new.png"
    old_pdf = assets / "old.pdf"
    new_pdf = assets / "new.pdf"
    old_image.write_bytes(b"old")
    new_image.write_bytes(b"new")
    old_pdf.write_bytes(b"old")
    new_pdf.write_bytes(b"new")

    source = docs / "main.tex"
    source.write_text(
        "\\includegraphics{../assets/old.png}\n"
        "\\includepdf{../assets/old.pdf}\n",
        encoding="utf-8",
    )

    changed = PathReferenceUpdater.update_workspace_reference_mappings(
        repository_root,
        [(old_image, new_image), (old_pdf, new_pdf)],
    )

    assert source.resolve() in changed
    text = source.read_text(encoding="utf-8")
    assert "../assets/new.png" in text
    assert "../assets/new.pdf" in text


def test_repo_alias_is_preserved_after_move(tmp_path: Path) -> None:
    """Keep /repo references portable instead of expanding them to a machine-specific absolute path."""
    repository_root = tmp_path / "repo"
    project = repository_root / "project"
    project.mkdir(parents=True)
    old_target = project / "before.tex"
    new_target = project / "after.tex"
    old_target.write_text("before", encoding="utf-8")
    new_target.write_text("after", encoding="utf-8")
    source = project / "main.tex"
    source.write_text(
        "\\href{/repo/project/before.tex}{open}\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        repository_root,
        old_target,
        new_target,
    )

    assert source.read_text(encoding="utf-8") == (
        "\\href{/repo/project/after.tex}{open}\n"
    )


def test_excluded_open_file_is_not_written_by_background_batch(tmp_path: Path) -> None:
    """Leave open editor files to the GUI-side merge so the child process cannot race typing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    old_target = workspace / "old.tex"
    new_target = workspace / "new.tex"
    old_target.write_text("old", encoding="utf-8")
    new_target.write_text("new", encoding="utf-8")
    source = workspace / "main.tex"
    source.write_text("\\input{old}\n", encoding="utf-8")

    changed = PathReferenceUpdater.update_workspace_reference_mappings(
        workspace,
        [(old_target, new_target)],
        exclude_files=[source],
    )

    assert changed == []
    assert source.read_text(encoding="utf-8") == "\\input{old}\n"
