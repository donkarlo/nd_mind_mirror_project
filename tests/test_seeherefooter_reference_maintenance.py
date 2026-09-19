r"""Regression coverage for rename/delete maintenance of ``\seeherefooter``."""

from pathlib import Path

from nd_mind_mirror.core.workspace.path.path_reference_updater import (
    PathReferenceUpdater,
)
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


def test_rename_rewrites_only_seeherefooter_argument(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    assets = workspace / "assets"
    docs.mkdir(parents=True)
    assets.mkdir()

    old_file = assets / "before.txt"
    new_file = assets / "after.txt"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")
    source_file = docs / "main.tex"
    source_file.write_text(
        "\\seeherefooter{../assets/before.txt}\n"
        "Plain: ../assets/before.txt\n",
        encoding="utf-8",
    )

    PathReferenceUpdater.update_workspace_references(
        workspace,
        old_file,
        new_file,
    )

    source = source_file.read_text(encoding="utf-8")
    assert "\\seeherefooter{../assets/after.txt}" in source
    assert "Plain: ../assets/before.txt" in source


def test_find_usages_detects_seeherefooter_target(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("x", encoding="utf-8")
    source_file = workspace / "main.tex"
    source_file.write_text(
        "\\seeherefooter{/target.txt}\n",
        encoding="utf-8",
    )

    resolver = WorkspaceReferenceResolver(workspace)
    usages = resolver.find_usages(workspace, target)

    assert len(usages) == 1
    assert usages[0].command == "seeherefooter"
    assert usages[0].target_path == target.resolve()


def test_delete_removes_complete_seeherefooter_tag(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("x", encoding="utf-8")
    source_file = workspace / "main.tex"
    source = (
        "Before\n"
        "\\seeherefooter{/target.txt}\n"
        "After\n"
    )

    resolver = WorkspaceReferenceResolver(workspace)
    updated = resolver.remove_references(
        source,
        source_file,
        target,
    )

    assert "\\seeherefooter" not in updated
    assert "/target.txt" not in updated
    assert "Before" in updated
    assert "After" in updated
