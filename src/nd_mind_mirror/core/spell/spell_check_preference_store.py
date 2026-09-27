"""Per-file persisted spell-check preferences."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QSettings


class SpellCheckPreferenceStore:
    """Persist spell-check enablement and one language mode per source file."""

    _VALID_LANGUAGES = {"auto", "en", "de", "fa"}

    def __init__(self, settings_path: str | Path) -> None:
        self._settings = QSettings(
            str(Path(settings_path).expanduser()),
            QSettings.Format.IniFormat,
        )

    @staticmethod
    def _prefix(path: str | Path) -> str:
        canonical = str(Path(path).expanduser().resolve())
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"spell_check/files/{digest}"

    def is_enabled(self, path: str | Path) -> bool:
        return self._settings.value(
            f"{self._prefix(path)}/enabled",
            False,
            type=bool,
        )

    def set_enabled(self, path: str | Path, enabled: bool) -> None:
        self._settings.setValue(
            f"{self._prefix(path)}/enabled",
            bool(enabled),
        )
        self._settings.sync()

    def language(self, path: str | Path) -> str:
        value = str(
            self._settings.value(
                f"{self._prefix(path)}/language",
                "auto",
            )
        ).strip().casefold()
        return value if value in self._VALID_LANGUAGES else "auto"

    def set_language(self, path: str | Path, language: str) -> None:
        value = str(language).strip().casefold()
        if value not in self._VALID_LANGUAGES:
            raise ValueError(f"Unsupported spell-check language: {language}")
        self._settings.setValue(
            f"{self._prefix(path)}/language",
            value,
        )
        self._settings.sync()

    def remap(self, old_path: str | Path, new_path: str | Path) -> None:
        old_prefix = self._prefix(old_path)
        new_prefix = self._prefix(new_path)
        self._settings.setValue(
            f"{new_prefix}/enabled",
            self.is_enabled(old_path),
        )
        self._settings.setValue(
            f"{new_prefix}/language",
            self.language(old_path),
        )
        self._settings.remove(old_prefix)
        self._settings.sync()
