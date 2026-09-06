"""Regression tests for process-side workspace move/delete batches."""

from pathlib import Path

from nd_mind_mirror.core.workspace.operation.filesystem_operation_service import (
    WorkspaceFilesystemOperationService,
)


def test_moves_multiple_paths_in_one_request(tmp_path: Path) -> None:
    """Move multiple selected files to exact destinations in one service batch."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    first = source / "first.tex"
    second = source / "second.png"
    first.write_text("first", encoding="utf-8")
    second.write_bytes(b"png")

    result = WorkspaceFilesystemOperationService().execute(
        {
            "moves": [
                {"source": str(first), "destination": str(destination / first.name)},
                {"source": str(second), "destination": str(destination / second.name)},
            ],
            "deletes": [],
        }
    )

    assert [item["success"] for item in result["moves"]] == [True, True]
    assert not first.exists()
    assert not second.exists()
    assert (destination / "first.tex").read_text(encoding="utf-8") == "first"
    assert (destination / "second.png").read_bytes() == b"png"


def test_deletes_multiple_files_and_folders_in_one_request(tmp_path: Path) -> None:
    """Delete a mixed file/folder selection without stopping after the first entry."""
    file_path = tmp_path / "note.tex"
    folder_path = tmp_path / "folder"
    nested = folder_path / "nested.txt"
    folder_path.mkdir()
    file_path.write_text("note", encoding="utf-8")
    nested.write_text("nested", encoding="utf-8")

    result = WorkspaceFilesystemOperationService().execute(
        {
            "moves": [],
            "deletes": [str(file_path), str(folder_path)],
        }
    )

    assert [item["success"] for item in result["deletes"]] == [True, True]
    assert not file_path.exists()
    assert not folder_path.exists()


def test_move_failure_does_not_abort_later_entries(tmp_path: Path) -> None:
    """Report a conflicting destination while continuing independent move entries."""
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    conflict_source = source / "conflict.tex"
    success_source = source / "success.tex"
    conflict_target = destination / "conflict.tex"
    conflict_source.write_text("source", encoding="utf-8")
    success_source.write_text("success", encoding="utf-8")
    conflict_target.write_text("existing", encoding="utf-8")

    result = WorkspaceFilesystemOperationService().execute(
        {
            "moves": [
                {
                    "source": str(conflict_source),
                    "destination": str(conflict_target),
                },
                {
                    "source": str(success_source),
                    "destination": str(destination / "success.tex"),
                },
            ],
            "deletes": [],
        }
    )

    assert result["moves"][0]["success"] is False
    assert result["moves"][1]["success"] is True
    assert conflict_source.exists()
    assert (destination / "success.tex").exists()
