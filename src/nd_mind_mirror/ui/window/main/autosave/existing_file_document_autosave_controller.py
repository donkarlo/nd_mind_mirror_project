"""Autosave controller that never recreates a file deleted outside Mind Mirror."""

import os
from pathlib import Path

from nd_mind_mirror.ui.window.main.autosave.low_sync_document_autosave_controller import (
    LowSyncDocumentAutosaveController,
)


class ExistingFileDocumentAutosaveController(LowSyncDocumentAutosaveController):
    """Commit snapshots only while the canonical destination still exists."""

    def _on_write_finished(
        self,
        raw_path: str,
        revision: int,
        success: bool,
        _message: str,
        raw_temporary: str,
    ) -> None:
        source_path = Path(raw_path).expanduser().resolve(strict=False)
        destination = self._pending_destinations.pop(source_path, source_path)
        self._pending_paths.discard(source_path)
        temporary = Path(raw_temporary) if raw_temporary else None

        if not success or temporary is None or destination is None:
            self._remove_temp(temporary)
            return

        destination = destination.expanduser().resolve(strict=False)
        # External deletion is authoritative. Autosave must never turn a stale
        # open editor buffer into a newly recreated filesystem object.
        if not destination.is_file() or not destination.parent.is_dir():
            self._remove_temp(temporary)
            return

        if not self._editor_panel.autosave_revision_matches(destination, revision):
            self._remove_temp(temporary)
            return

        try:
            os.replace(temporary, destination)
        except OSError:
            self._remove_temp(temporary)
            return

        self._on_written(destination)
        self._editor_panel.mark_saved(destination)
