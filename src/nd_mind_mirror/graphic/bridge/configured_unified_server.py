"""Shared graphic bridge configured with responsive source-backed TikZ editing."""

from __future__ import annotations

import asyncio
from pathlib import Path
import time

from nd_mind_mirror.graphic.bridge.responsive_unified_server import (
    ResponsiveUnifiedGraphicBridgeServer,
)
from nd_mind_mirror.graphic.tikz.bridge.tikz_canvas_settings import (
    TikZCanvasSettings,
)


class ConfiguredUnifiedGraphicBridgeServer(ResponsiveUnifiedGraphicBridgeServer):
    """Run the shared bridge with bounded polling and idle-only TikZ rendering."""

    _OPEN_REQUEST_POLL_SECONDS = 0.50
    _RENAME_REQUEST_POLL_SECONDS = 0.50
    _TIKZ_OPEN_REQUEST_POLL_SECONDS = 0.50
    _ACTIVE_FILE_POLL_SECONDS = 0.50
    _IDLE_DISCOVERY_SLEEP_SECONDS = 1.00
    _FAILED_DISCOVERY_SLEEP_SECONDS = 2.50
    _EXPLICIT_TIKZ_RENDER_IDLE_SECONDS = 1.00

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._watched_file_signatures: dict[Path, tuple[int, int] | None] = {}
        self._pending_tikz_render_task: asyncio.Task[None] | None = None
        self._pending_tikz_render_writer = None
        self._pending_tikz_render_path: Path | None = None

    async def startup(self) -> None:
        """Treat the durable request that launched this on-demand bridge as pending."""
        await super().startup()
        self._last_delivered_open_request_mtime_ns = 0

    async def shutdown(self) -> None:
        """Cancel an idle render before shutting down inherited transports."""
        task = self._pending_tikz_render_task
        self._pending_tikz_render_task = None
        self._pending_tikz_render_writer = None
        self._pending_tikz_render_path = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await super().shutdown()

    async def _send_tikz_open(self, writer, path: Path) -> None:
        """Open TikZ source immediately without starting LuaLaTeX."""
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
            f"Sent source-only TikZ editor open path={path} "
            f"canvas={canvas.width}x{canvas.height}"
        )

    async def _send_tikz_render(self, writer, path: Path) -> None:
        """Coalesce explicit render requests and render only after input is idle."""
        self._pending_tikz_render_writer = writer
        self._pending_tikz_render_path = path.resolve()

        previous = self._pending_tikz_render_task
        if previous is not None:
            previous.cancel()

        task = asyncio.create_task(self._render_pending_tikz_after_idle())
        self._pending_tikz_render_task = task

    async def _render_pending_tikz_after_idle(self) -> None:
        """Run at most one expensive renderer for the newest explicit request."""
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(self._EXPLICIT_TIKZ_RENDER_IDLE_SECONDS)
            writer = self._pending_tikz_render_writer
            path = self._pending_tikz_render_path
            if writer is None or path is None:
                return
            await super()._send_tikz_render(writer, path)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._log_event(
                f"Idle TikZ render error: {type(exc).__name__}: {exc}"
            )
        finally:
            if self._pending_tikz_render_task is current_task:
                self._pending_tikz_render_task = None
                self._pending_tikz_render_writer = None
                self._pending_tikz_render_path = None

    async def _reverse_connector_loop(self) -> None:
        """Scan the LAN only while a desktop request is waiting for an iPad."""
        while True:
            try:
                if self.tcp_clients or not self._has_pending_editor_request():
                    await asyncio.sleep(self._IDLE_DISCOVERY_SLEEP_SECONDS)
                    continue

                found = await self._discover_ipad_listener()
                if found is None:
                    await asyncio.sleep(self._FAILED_DISCOVERY_SLEEP_SECONDS)
                    continue

                host, reader, writer, greeting = found
                await self._serve_reverse_ipad(host, reader, writer, greeting)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_event(
                    f"Reverse iPad discovery error: {type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(self._FAILED_DISCOVERY_SLEEP_SECONDS)

    async def _watch_workspace(self) -> None:
        """Watch only the active sidecar and image instead of the whole repository."""
        while True:
            try:
                await self._poll_active_graphic_files()
                await asyncio.sleep(self._ACTIVE_FILE_POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_event(
                    f"Active graphic watcher error: {type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(1.0)

    async def _poll_active_graphic_files(self) -> None:
        sidecar = self.current_sidecar
        if sidecar is None or not sidecar.is_file():
            self._watched_file_signatures.clear()
            return

        try:
            _document, image = self._read_document(sidecar)
        except Exception:
            return

        watched = (sidecar.resolve(), image.resolve())
        active_set = set(watched)
        self._watched_file_signatures = {
            path: signature
            for path, signature in self._watched_file_signatures.items()
            if path in active_set
        }

        changed_for_real = False
        now = time.monotonic()
        for path in watched:
            signature = self._file_signature(path)
            previous = self._watched_file_signatures.get(path)
            self._watched_file_signatures[path] = signature
            if signature is None or previous is None or signature == previous:
                continue

            if now < self._suppress_broadcast_until.get(path, 0.0):
                continue
            changed_for_real = True

        if changed_for_real:
            await self._broadcast_open(
                sidecar,
                "graphic_updated",
                operation=self.current_operation,
            )

    def _has_pending_editor_request(self) -> bool:
        graphic = self._current_open_request()
        if (
            graphic is not None
            and graphic[0] > self._last_delivered_open_request_mtime_ns
        ):
            return True

        tikz = self._current_tikz_request()
        return bool(
            tikz is not None
            and tikz[0] > self._last_delivered_tikz_open_request_mtime_ns
        )

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_size)
