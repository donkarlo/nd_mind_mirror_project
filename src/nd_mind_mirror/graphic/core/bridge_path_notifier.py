"""Notify the local graphic bridge when a managed workspace path is renamed."""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GraphicBridgePathNotifier:
    """Persist rename events and also nudge the running bridge over HTTP."""

    def __init__(
        self,
        workspace_root: str | Path,
        bridge_http_url: str,
        token: str = "",
    ) -> None:
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._bridge_http_url = str(bridge_http_url).rstrip("/")
        self._token = str(token)
        self._request_path = (
            self._workspace_root
            / ".nd_mind_mirror"
            / "graphic_rename_request.json"
        )

    def notify_rename(self, old_path: str | Path, new_path: str | Path) -> bool:
        """Persist one rename before sending the best-effort low-latency HTTP nudge."""
        try:
            old_relative = self._relative_path(old_path)
            new_relative = self._relative_path(new_path)
        except ValueError:
            return False
        if old_relative == new_relative:
            return False

        payload = {
            "old_path": old_relative,
            "new_path": new_relative,
            "request_id": time.time_ns(),
        }
        durable_written = self._write_durable_request(payload)

        thread = threading.Thread(
            target=self._send,
            args=(payload,),
            name="nd-graphic-path-notifier",
            daemon=True,
        )
        thread.start()
        return durable_written

    def _relative_path(self, path: str | Path) -> str:
        """Return a portable path relative to the configured bridge workspace."""
        resolved = Path(path).expanduser().resolve(strict=False)
        return resolved.relative_to(self._workspace_root).as_posix()

    def _write_durable_request(self, payload: dict[str, object]) -> bool:
        """Atomically persist the newest rename so HTTP/port failures cannot lose it."""
        try:
            self._request_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._request_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(self._request_path)
            return True
        except OSError:
            return False

    def _send(self, payload: dict[str, object]) -> None:
        """Post one compact rename event when the configured HTTP bridge is reachable."""
        if not self._bridge_http_url:
            return
        endpoint = f"{self._bridge_http_url}/rename-graphic"
        if self._token:
            endpoint += "?" + urlencode({"token": self._token})
        try:
            request = Request(
                endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=1.0) as response:
                response.read(256)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return
