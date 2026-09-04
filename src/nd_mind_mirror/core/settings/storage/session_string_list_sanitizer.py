from __future__ import annotations


class SessionStringListSanitizer:
    """Keep QSettings string-list values readable across empty/invalid states."""

    def __init__(self, settings) -> None:
        self._settings = settings

    def normalize_many(self, keys: tuple[str, ...] | list[str]) -> None:
        for key in keys:
            self.normalize(key)

    def normalize(self, key: str) -> None:
        """Replace invalid or empty Qt list values with a safe empty string."""
        setting_key = str(key)
        value = self._settings.value(setting_key, None)
        normalized = self._normalized_value(value)

        if normalized == value and isinstance(value, (str, list)):
            return
        self._settings.setValue(setting_key, normalized)

    @staticmethod
    def _normalized_value(value):
        if isinstance(value, str):
            return value

        if isinstance(value, (list, tuple)):
            items = [
                str(item)
                for item in value
                if item is not None and str(item)
            ]
            return items if items else ""

        return ""
