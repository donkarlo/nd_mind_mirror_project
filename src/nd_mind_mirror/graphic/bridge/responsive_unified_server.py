"""Responsive TikZ saves layered over the shared image/TikZ bridge."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import Any

from nd_mind_mirror.graphic.bridge.unified_server import UnifiedGraphicBridgeServer


class ResponsiveUnifiedGraphicBridgeServer(UnifiedGraphicBridgeServer):
    """Acknowledge TikZ source saves immediately and render previews in background."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tikz_update_event_path = (
            self.workspace / ".nd_mind_mirror" / "tikz_update_event.json"
        )

    async def _update_tikz(self, writer, payload: dict[str, Any]) -> None:
        """Persist source, notify Ubuntu, ACK the iPad, then render asynchronously."""
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

        self._schedule_tikz_render(
            writer,
            path,
            source,
            client_revision=revision,
        )

    def _write_tikz_update_event(self, relative_path: str, revision: int) -> None:
        """Publish one tiny atomic event so Source, Visual, and Preview refresh quickly."""
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

    def _schedule_tikz_render(
        self,
        writer,
        path: Path,
        source: str,
        client_revision: int = 0,
    ) -> None:
        """Track a non-blocking render and preserve its source revision."""
        task = asyncio.create_task(
            self._render_and_send_tikz_preview(
                writer,
                path,
                source,
                client_revision=client_revision,
            )
        )
        self._tikz_render_tasks.add(task)
        task.add_done_callback(self._tikz_render_tasks.discard)

    async def _render_and_send_tikz_preview(
        self,
        writer,
        path: Path,
        source: str,
        client_revision: int = 0,
    ) -> None:
        """Render off the event loop without delaying the canonical source save ACK."""
        relative = path.relative_to(self.workspace).as_posix()
        payload: dict[str, Any] = {
            "type": "tikz_rendered",
            "path": relative,
            "source": source,
            "client_revision": int(client_revision),
        }
        try:
            rendered = await asyncio.to_thread(self._tikz_renderer.render, source, path)
            payload["preview_png_base64"] = rendered.png_base64
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            payload["message"] = f"TikZ render failed: {exc}"
        try:
            await self._send_tcp(writer, payload)
        except (ConnectionError, BrokenPipeError, OSError):
            return
