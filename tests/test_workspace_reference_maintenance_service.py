"""Regression tests for child-process reference maintenance after confirmed deletes."""

from pathlib import Path

from nd_mind_mirror.core.workspace.operation.reference_maintenance_service import (
    WorkspaceReferenceMaintenanceService,
)


def test_delete_reference_maintenance_uses_preflight_referring_files(tmp_path: Path) -> None:
    """Remove only references from the files supplied by the already-completed delete preflight."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "image.png"
    source = workspace / "main.tex"
    untouched = workspace / "other.tex"
    source.write_text(
        "before\n"
        "\\begin{figure}\n"
        "\\includegraphics{image.png}\n"
        "\\end{figure}\n"
        "after\n",
        encoding="utf-8",
    )
    untouched.write_text("\\includegraphics{image.png}\n", encoding="utf-8")

    result = WorkspaceReferenceMaintenanceService().execute(
        {
            "workspace_root": str(workspace),
            "deletions": [
                {
                    "target": str(target),
                    "files": [str(source)],
                }
            ],
            "moves": [],
            "exclude_files": [],
        }
    )

    assert result["errors"] == []
    assert str(source.resolve()) in result["changed_files"]
    assert "includegraphics" not in source.read_text(encoding="utf-8")
    assert "includegraphics" in untouched.read_text(encoding="utf-8")
