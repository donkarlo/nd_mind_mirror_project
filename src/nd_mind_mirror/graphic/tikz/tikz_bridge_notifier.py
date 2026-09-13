"""Notify the local TikZ bridge when the desktop requests an iPad file open."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from urllib import request

from .tikz_document_manager import TikZDocumentManager


class TikZBridgeNotifier:
    """Send non-blocking desktop-open requests to the isolated TikZ bridge."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        bridge_http_url: str = "http://127.0.0.1:8765",
    ) -> None:
        self._manager = TikZDocumentManager(workspace_root)
        self._bridge_http_url = str(bridge_http_url).rstrip("/")

    def open_on_ipad(self, source_path: str | Path) -> None:
        """Request an iPad open without blocking the Qt event loop."""
        relative = self._manager.workspace_relative_path(source_path)
        Thread(
            target=self._post_open,
            args=(relative,),
            name="nd-tikz-desktop-open-notifier",
            daemon=True,
        ).start()

    def _post_open(self, relative: str) -> None:
        """Post one bridge request; bridge availability is intentionally best-effort."""
        payload = json.dumps({"path": relative}).encode("utf-8")
        http_request = request.Request(
            f"{self._bridge_http_url}/desktop/open",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=1.5):
                return
        except (OSError, ValueError):
            return
