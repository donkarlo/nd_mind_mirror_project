"""Notify the shared Mind Mirror iPad bridge to open a TikZ source."""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from nd_mind_mirror.graphic.core.bridge_process_manager import (
    GraphicBridgeProcessManager,
)

from .tikz_document_manager import TikZDocumentManager


class TikZBridgeNotifier:
    """Publish TikZ open requests and start the shared bridge only when needed."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        bridge_http_url: str = "http://127.0.0.1:8766",
        token: str = "",
    ) -> None:
        self._manager = TikZDocumentManager(workspace_root)
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._bridge_http_url = str(bridge_http_url).rstrip("/")
        self._token = str(token)
        self._request_path = (
            self._workspace_root / ".nd_mind_mirror" / "tikz_open_request.json"
        )
        self._process_manager = GraphicBridgeProcessManager(
            workspace_root=self._workspace_root,
        )

    def open_on_ipad(self, source_path: str | Path) -> None:
        """Persist the TikZ request and ensure the canonical bridge is running."""
        relative = self._manager.workspace_relative_path(source_path)
        payload = {"path": relative}
        self._request_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._request_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self._request_path)
        self._process_manager.start_if_needed()
        threading.Thread(
            target=self._post_best_effort,
            args=(payload,),
            name="nd-shared-bridge-tikz-open",
            daemon=True,
        ).start()

    def _post_best_effort(self, payload: dict[str, str]) -> None:
        if not self._bridge_http_url:
            return
        url = self._bridge_http_url + "/open-tikz"
        if self._token:
            separator = "&" if "?" in url else "?"
            url += separator + "token=" + urllib.parse.quote(self._token)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(4):
            try:
                urllib.request.urlopen(request, timeout=0.45).read(16)
                return
            except (OSError, urllib.error.URLError, ValueError):
                if attempt < 3:
                    time.sleep(0.20)
