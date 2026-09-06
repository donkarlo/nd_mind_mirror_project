"""Stage autosave snapshots outside Dropbox before the final atomic commit."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from nd_mind_mirror.ui.window.main.autosave.document_autosave_controller import (
    DocumentAutosaveController,
)


class LowSyncDocumentAutosaveController(DocumentAutosaveController):
    """Avoid Dropbox-visible temporary-file churn during background autosave."""

    _STAGING_DIRECTORY = (
        Path.home() / ".cache" / "nd_mind_mirror_project" / "autosave_staging"
    )

    @classmethod
    def _write_snapshot_to_temp(cls, path: Path, pieces: tuple[str, ...]) -> Path:
        """Write the immutable snapshot to local application cache, not Dropbox."""
        cls._STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
        original_mode: int | None = None
        try:
            try:
                original_mode = path.stat().st_mode
            except OSError:
                original_mode = None

            descriptor, raw_temporary = tempfile.mkstemp(
                prefix="snapshot_",
                suffix=".tmp",
                dir=cls._STAGING_DIRECTORY,
                text=True,
            )
            temporary = Path(raw_temporary)
            try:
                with os.fdopen(
                    descriptor,
                    "w",
                    encoding="utf-8",
                    newline="",
                ) as handle:
                    for piece in pieces:
                        handle.write(piece)
                    handle.flush()
                    os.fsync(handle.fileno())
                if original_mode is not None:
                    os.chmod(temporary, original_mode)
                return temporary
            except Exception:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
                raise
        except Exception:
            raise
