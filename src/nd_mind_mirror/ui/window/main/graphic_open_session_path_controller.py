"""Synchronize managed graphic renames with the currently open iPad document."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from nd_mind_mirror.graphic.core.bridge_path_notifier import GraphicBridgePathNotifier


class GraphicOpenSessionPathController(QObject):
    """Repair moved sidecar metadata and notify the bridge after Navigator renames."""

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self._window = window
        self._notifier = self._create_notifier()
        window._file_system_panel.path_renamed.connect(self._on_path_renamed)

    def reload_settings(self) -> None:
        """Rebuild the notifier after settings.yaml changes."""
        self._notifier = self._create_notifier()

    @Slot(str, str)
    def _on_path_renamed(self, old_path: str, new_path: str) -> None:
        """Handle folders and managed sidecars after their filesystem move completes."""
        old = Path(old_path).expanduser().resolve(strict=False)
        new = Path(new_path).expanduser().resolve(strict=False)
        if new.suffix.lower() == ".ndgraphic":
            self._repair_sidecar_image_name(new)
            self._notifier.notify_rename(old, new)
            return
        if new.is_dir():
            self._notifier.notify_rename(old, new)

    def _create_notifier(self) -> GraphicBridgePathNotifier:
        """Build a notifier from the current Ubuntu application settings."""
        settings = self._window._app_settings
        return GraphicBridgePathNotifier(
            settings.search_default_path,
            settings.graphic_bridge_http_url,
            settings.graphic_bridge_token,
        )

    @staticmethod
    def _repair_sidecar_image_name(sidecar_path: Path) -> None:
        """Retarget a renamed sidecar to a same-stem image when that image exists."""
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
            old_image_name = str(data.get("image_name", "")).strip()
            suffix = Path(old_image_name).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg"}:
                return
            candidate = sidecar_path.with_suffix(suffix)
            if not candidate.is_file() or data.get("image_name") == candidate.name:
                return
            data["image_name"] = candidate.name
            sidecar_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return
