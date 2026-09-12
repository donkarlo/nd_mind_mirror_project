"""Coordinate BibTeX duplicate diagnostics and paste protection in the editor."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from nd_mind_mirror.core.bibliography.bibtex_duplicate_key_validator import (
    BibtexDuplicateKeyValidator,
)
from nd_mind_mirror.core.bibliography.bibtex_paste_guard import BibtexPasteGuard

if TYPE_CHECKING:
    from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor


class BibtexIntegrityController(QObject):
    """Apply BibTeX-only duplicate-key rules without affecting other text files."""

    _MAX_KEYS_IN_DIALOG = 12

    def __init__(
        self,
        editor: "GenericTextEditor",
        source_path: str | Path,
    ) -> None:
        super().__init__(editor)
        self._editor = editor
        self._source_path = Path(source_path).expanduser().resolve(strict=False)
        self._validator = BibtexDuplicateKeyValidator()
        self._paste_guard = BibtexPasteGuard()
        self._last_reported_signature: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        """Return True only for BibTeX database files."""
        return self._source_path.suffix.lower() == ".bib"

    def set_source_path(self, source_path: str | Path) -> None:
        """Follow editor renames and reset diagnostics outside ``.bib`` files."""
        self._source_path = Path(source_path).expanduser().resolve(strict=False)
        if not self.enabled:
            self._last_reported_signature = ()

    def validate_document(self, source: str) -> None:
        """Report newly observed duplicate keys in an already-existing BibTeX file."""
        if not self.enabled:
            return

        duplicates = self._validator.duplicates(source)
        signature = tuple(duplicates)
        if not signature:
            self._last_reported_signature = ()
            return
        if signature == self._last_reported_signature:
            return

        self._last_reported_signature = signature
        QMessageBox.critical(
            self._editor,
            "BibTeX duplicate entries",
            self._existing_duplicate_message(duplicates),
        )

    def allow_paste(
        self,
        document_source: str,
        selection_start: int,
        selection_end: int,
        pasted_text: str,
    ) -> bool:
        """Return False and explain when one paste would introduce duplicate keys."""
        if not self.enabled:
            return True

        conflicts = self._paste_guard.conflicts(
            document_source,
            selection_start,
            selection_end,
            pasted_text,
        )
        if not conflicts:
            return True

        QMessageBox.warning(
            self._editor,
            "BibTeX paste blocked",
            self._paste_conflict_message(conflicts),
        )
        return False

    def _existing_duplicate_message(
        self,
        duplicates: dict[str, tuple[int, ...]],
    ) -> str:
        items = list(duplicates.items())
        visible = items[: self._MAX_KEYS_IN_DIALOG]
        lines = [
            "This .bib file contains duplicate BibTeX entry keys:",
            "",
        ]
        for key, occurrences in visible:
            line_text = ", ".join(str(line) for line in occurrences)
            lines.append(f"• {key} — lines {line_text}")
        if len(items) > len(visible):
            lines.append(f"• … and {len(items) - len(visible)} more")
        lines.extend(("", "Each BibTeX entry key must be unique."))
        return "\n".join(lines)

    def _paste_conflict_message(self, conflicts: tuple[str, ...]) -> str:
        visible = conflicts[: self._MAX_KEYS_IN_DIALOG]
        lines = [
            "Paste was blocked because it would create duplicate BibTeX entry keys:",
            "",
        ]
        lines.extend(f"• {key}" for key in visible)
        if len(conflicts) > len(visible):
            lines.append(f"• … and {len(conflicts) - len(visible)} more")
        lines.extend(("", "No text was inserted."))
        return "\n".join(lines)
