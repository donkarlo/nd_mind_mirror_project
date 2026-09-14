"""Shared graphic bridge configured with responsive source-backed TikZ editing."""

from __future__ import annotations

from pathlib import Path

from nd_mind_mirror.graphic.bridge.responsive_unified_server import (
    ResponsiveUnifiedGraphicBridgeServer,
)
from nd_mind_mirror.graphic.tikz.bridge.tikz_canvas_settings import (
    TikZCanvasSettings,
)


class ConfiguredUnifiedGraphicBridgeServer(ResponsiveUnifiedGraphicBridgeServer):
    """Inject configured TikZ canvas metadata into the shared responsive transport."""

    async def _send_tikz_open(self, writer, path: Path) -> None:
        source = path.read_text(encoding="utf-8")
        canvas = TikZCanvasSettings.load(self.workspace)
        source_for_ipad = canvas.materialize_source(source)
        relative = path.relative_to(self.workspace).as_posix()
        await self._send_tcp(
            writer,
            {
                "type": "open_tikz",
                "path": relative,
                "source": source_for_ipad,
            },
        )
        self._log_event(
            f"Sent TikZ editor open path={path} canvas={canvas.width}x{canvas.height}"
        )
        self._schedule_tikz_render(writer, path, source)
