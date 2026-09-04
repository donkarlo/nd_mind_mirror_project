"""Compose enhanced window features with robust persistent-session handling."""

from nd_mind_mirror.core.settings.storage.session_string_list_sanitizer import (
    SessionStringListSanitizer,
)
from nd_mind_mirror.ui.window.main.enhanced_main_window_features import (
    EnhancedMainWindow as FeatureEnhancedMainWindow,
)


class EnhancedMainWindow(FeatureEnhancedMainWindow):
    """Run the enhanced window with safe QSettings string-list persistence."""

    _SESSION_STRING_LIST_KEYS = (
        "filesystem/expanded_paths",
        "editor/recent_files",
    )

    def _restore_session(self) -> None:
        """Normalize invalid Qt list values before the base restore reads them."""
        self._sanitize_session_string_lists()
        super()._restore_session()

    def _save_session(self) -> None:
        """Prevent empty Python lists from persisting as Qt @Invalid values."""
        super()._save_session()
        self._sanitize_session_string_lists()
        self._session_settings.sync()

    def _sanitize_session_string_lists(self) -> None:
        settings = getattr(self, "_session_settings", None)
        if settings is None:
            return
        SessionStringListSanitizer(settings).normalize_many(
            self._SESSION_STRING_LIST_KEYS
        )
