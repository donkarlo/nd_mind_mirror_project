from __future__ import annotations

from pathlib import Path
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from nd_mind_mirror.graphic.core.bridge_process_manager import (
    GraphicBridgeProcessManager,
)


class GraphicBridgeNotifier:
    """Publish one graphic request and start the shared iPad bridge on demand."""

    def __init__(
        self,
        *,
        workspace_root: str | Path,
        bridge_http_url: str = "http://127.0.0.1:8766",
        token: str = "",
    ) -> None:
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.bridge_http_url = str(bridge_http_url).rstrip("/")
        self.token = str(token)
        self.request_path = (
            self.workspace_root / ".nd_mind_mirror" / "graphic_open_request.json"
        )
        self._process_manager = GraphicBridgeProcessManager(
            workspace_root=self.workspace_root,
        )

    def request_open(
        self,
        sidecar_path: str | Path,
        *,
        operation: str = "update",
    ) -> str:
        """Persist the request, ensure one bridge exists, then nudge it over HTTP."""
        sidecar = Path(sidecar_path).expanduser().resolve()
        relative = sidecar.relative_to(self.workspace_root).as_posix()
        operation = "insert" if str(operation).lower() == "insert" else "update"
        payload = {"path": relative, "operation": operation}
        self.request_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.request_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload), encoding="utf-8")
        temp.replace(self.request_path)
        self._process_manager.start_if_needed()
        threading.Thread(
            target=self._post_best_effort,
            args=(payload,),
            name="nd-graphic-bridge-open",
            daemon=True,
        ).start()
        return relative

    def _post_best_effort(self, payload: dict[str, str]) -> None:
        if not self.bridge_http_url:
            return
        body = json.dumps(payload).encode("utf-8")
        url = self.bridge_http_url + "/open-graphic"
        if self.token:
            separator = "&" if "?" in url else "?"
            url += separator + "token=" + urllib.parse.quote(self.token)
        request = urllib.request.Request(
            url,
            data=body,
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
