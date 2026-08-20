from __future__ import annotations

from pathlib import Path
import json
import threading
import urllib.error
import urllib.request
import urllib.parse


class GraphicBridgeNotifier:
    """Publish the graphic that the iPad should open.

    The request file is durable and is enough on its own: the Ubuntu bridge
    watches it and also replays the latest request to an iPad that connects
    later.  The tiny HTTP POST is only a low-latency nudge when the bridge is
    already running.
    """

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

    def request_open(self, sidecar_path: str | Path, *, operation: str = "update") -> str:
        sidecar = Path(sidecar_path).expanduser().resolve()
        relative = sidecar.relative_to(self.workspace_root).as_posix()
        operation = "insert" if str(operation).lower() == "insert" else "update"
        payload = {"path": relative, "operation": operation}
        self.request_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.request_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload), encoding="utf-8")
        temp.replace(self.request_path)
        threading.Thread(
            target=self._post_best_effort,
            args=(payload,),
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
        try:
            urllib.request.urlopen(request, timeout=0.45).read(16)
        except (OSError, urllib.error.URLError, ValueError):
            return
