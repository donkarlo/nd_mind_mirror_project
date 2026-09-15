"""Low-latency TikZ saves layered over the shared image/TikZ bridge."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from nd_mind_mirror.graphic.bridge.unified_server import UnifiedGraphicBridgeServer


class ResponsiveUnifiedGraphicBridgeServer(UnifiedGraphicBridgeServer):
    """Save TikZ immediately without compiling a preview for every edit."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tikz_update_event_path = (
            self.workspace / ".nd_mind_mirror" / "tikz_update_event.json"
        )

    async def _update_tikz(self, writer, payload: dict[str, Any]) -> None:
        """Persist source, notify Ubuntu, and ACK without an automatic render."""
        path = self._resolve_tikz(str(payload.get("path", "")))
        source = str(payload.get("source", ""))
        if "\\begin{tikzpicture}" not in source:
            await self._send_tcp(
                writer,
                {
                    "type": "tikz_error",
                    "path": path.relative_to(self.workspace).as_posix(),
                    "message": "TikZ source must contain a tikzpicture environment",
                },
            )
            return

        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(source, encoding="utf-8")
        temporary.replace(path)

        revision = self._safe_int(payload.get("client_revision", 0))
        relative = path.relative_to(self.workspace).as_posix()
        self._write_tikz_update_event(relative, revision)

        await self._send_tcp(
            writer,
            {
                "type": "tikz_saved",
                "path": relative,
                "source": source,
                "client_revision": revision,
                "message": f"Saved — {relative}",
            },
        )
        self._log_event(f"Saved TikZ source path={path} revision={revision}")

    def _write_tikz_update_event(self, relative_path: str, revision: int) -> None:
        """Publish one tiny atomic event for the desktop live-refresh pipeline."""
        self.tikz_update_event_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "path": relative_path,
            "client_revision": int(revision),
            "timestamp_ns": time.time_ns(),
        }
        temporary = self.tikz_update_event_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(self.tikz_update_event_path)
