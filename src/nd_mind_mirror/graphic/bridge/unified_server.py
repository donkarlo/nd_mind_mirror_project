"""Unified iPad bridge for raster graphics and source-backed TikZ diagrams."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Request

from nd_mind_mirror.graphic.tikz.bridge.renderer import TikZRenderer

from .path_aware_server import PathAwareGraphicBridgeServer


class UnifiedGraphicBridgeServer(PathAwareGraphicBridgeServer):
    """Carry image and TikZ editor sessions over the same iPad TCP connection."""

    _TIKZ_OPEN_REQUEST_POLL_SECONDS = 0.15

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tikz_request_path = (
            self.workspace / ".nd_mind_mirror" / "tikz_open_request.json"
        )
        self._tikz_renderer = TikZRenderer(self.workspace)
        self._tikz_open_request_task: asyncio.Task[None] | None = None
        self._tikz_render_tasks: set[asyncio.Task[None]] = set()
        self._last_seen_tikz_open_request_mtime_ns = 0
        self._last_delivered_tikz_open_request_mtime_ns = 0
        self.app.post("/open-tikz")(self.http_open_tikz)

    async def startup(self) -> None:
        """Start shared transports while preserving the newest durable TikZ request."""
        initial_mtime = self._tikz_open_request_mtime_ns()
        self._last_seen_tikz_open_request_mtime_ns = initial_mtime
        # Match the image bridge semantics: the durable latest request is still
        # pending until it is actually delivered to an iPad connection.
        self._last_delivered_tikz_open_request_mtime_ns = 0
        await super().startup()
        self._tikz_open_request_task = asyncio.create_task(
            self._watch_explicit_tikz_open_requests()
        )

    async def shutdown(self) -> None:
        """Stop TikZ watchers/renders before inherited bridge transports."""
        if self._tikz_open_request_task is not None:
            self._tikz_open_request_task.cancel()
            try:
                await self._tikz_open_request_task
            except asyncio.CancelledError:
                pass
            self._tikz_open_request_task = None

        render_tasks = tuple(self._tikz_render_tasks)
        for task in render_tasks:
            task.cancel()
        if render_tasks:
            await asyncio.gather(*render_tasks, return_exceptions=True)
        self._tikz_render_tasks.clear()
        await super().shutdown()

    async def http_open_tikz(self, request: Request) -> dict[str, object]:
        """Open one canonical TikZ child in the already-connected iPad app."""
        if not self._authorized(request.query_params.get("token", "")):
            return {"ok": False, "error": "Invalid token"}
        payload = await request.json()
        path = self._resolve_tikz(str(payload.get("path", "")))
        request_mtime = self._tikz_open_request_mtime_ns()
        self._last_seen_tikz_open_request_mtime_ns = max(
            self._last_seen_tikz_open_request_mtime_ns,
            request_mtime,
        )
        if self.tcp_clients:
            await self._broadcast_tikz_open(path)
            self._last_delivered_tikz_open_request_mtime_ns = max(
                self._last_delivered_tikz_open_request_mtime_ns,
                request_mtime,
            )
        self._log_event(f"Queued TikZ iPad open request path={path}")
        return {"ok": True, "path": path.relative_to(self.workspace).as_posix()}

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        greeting: dict[str, Any],
    ) -> None:
        """Use one reverse TCP session and route the newest explicit editor request."""
        version = str(greeting.get("version", "unknown"))
        self._log_event(
            f"Reverse iPad listener discovered at {host}:{self.ipad_listener_port} "
            f"version={version}; waiting for image or TikZ request"
        )
        self.tcp_clients.add(writer)
        try:
            await self._send_tcp(writer, {"type": "hello", "version": self.app.version})
            await self._deliver_latest_pending_editor_request(writer)
            while True:
                payload = await self._read_tcp_json(reader)
                await self._handle_tcp(writer, payload)
        except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError) as exc:
            self._log_event(
                f"Reverse iPad connection closed {host}:{self.ipad_listener_port}: "
                f"{type(exc).__name__}"
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._log_event(
                f"Reverse iPad connection error {host}:{self.ipad_listener_port}: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            self.tcp_clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_tcp(self, writer, payload: dict[str, Any]) -> None:
        """Route TikZ messages before falling back to the raster bridge protocol."""
        message_type = str(payload.get("type", ""))
        if message_type == "update_tikz":
            await self._update_tikz(writer, payload)
            return
        if message_type == "render_tikz":
            path = self._resolve_tikz(str(payload.get("path", "")))
            await self._send_tikz_render(writer, path)
            return
        await super()._handle_tcp(writer, payload)

    async def _update_tikz(self, writer, payload: dict[str, Any]) -> None:
        """Atomically save canonical TikZ source and return its refreshed preview."""
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
        response: dict[str, Any] = {
            "type": "tikz_saved",
            "path": relative,
            "source": source,
            "client_revision": revision,
            "message": f"Saved — {relative}",
        }
        try:
            rendered = await asyncio.to_thread(self._tikz_renderer.render, source, path)
            response["preview_png_base64"] = rendered.png_base64
        except Exception as exc:
            response["message"] = f"Saved; render failed: {exc}"
        await self._send_tcp(writer, response)
        self._log_event(f"Saved TikZ source path={path} revision={revision}")

    async def _watch_explicit_tikz_open_requests(self) -> None:
        """Deliver durable desktop TikZ requests even when HTTP uses a fallback port."""
        while True:
            try:
                request = self._current_tikz_request()
                if request is not None:
                    request_mtime, path = request
                    if request_mtime > self._last_seen_tikz_open_request_mtime_ns:
                        self._last_seen_tikz_open_request_mtime_ns = request_mtime
                        if self.tcp_clients:
                            await self._broadcast_tikz_open(path)
                            self._last_delivered_tikz_open_request_mtime_ns = request_mtime
                            self._log_event(
                                f"Delivered explicit TikZ iPad open request path={path}"
                            )
                        else:
                            self._log_event(
                                f"Queued explicit TikZ iPad open request until connection path={path}"
                            )
                await asyncio.sleep(self._TIKZ_OPEN_REQUEST_POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_event(
                    f"Explicit TikZ open request watcher error: {type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(0.5)

    async def _deliver_latest_pending_editor_request(self, writer) -> None:
        """Deliver whichever durable image/TikZ request is newest and still pending."""
        graphic_request = self._current_open_request()
        tikz_request = self._current_tikz_request()

        graphic_pending = (
            graphic_request is not None
            and graphic_request[0] > self._last_delivered_open_request_mtime_ns
        )
        tikz_pending = (
            tikz_request is not None
            and tikz_request[0] > self._last_delivered_tikz_open_request_mtime_ns
        )

        if not graphic_pending and not tikz_pending:
            return

        if tikz_pending and (
            not graphic_pending
            or tikz_request[0] >= graphic_request[0]  # type: ignore[index]
        ):
            request_mtime, path = tikz_request  # type: ignore[misc]
            await self._send_tikz_open(writer, path)
            self._last_seen_tikz_open_request_mtime_ns = max(
                self._last_seen_tikz_open_request_mtime_ns,
                request_mtime,
            )
            self._last_delivered_tikz_open_request_mtime_ns = request_mtime
            return

        request_mtime, sidecar, operation = graphic_request  # type: ignore[misc]
        self.current_sidecar = sidecar
        self.current_operation = operation
        await self._send_open_tcp(
            writer,
            sidecar,
            "open_graphic",
            operation=operation,
        )
        self._last_seen_open_request_mtime_ns = max(
            self._last_seen_open_request_mtime_ns,
            request_mtime,
        )
        self._last_delivered_open_request_mtime_ns = request_mtime

    async def _broadcast_tikz_open(self, path: Path) -> None:
        """Open TikZ immediately on every connected native iPad transport."""
        for writer in tuple(self.tcp_clients):
            try:
                await self._send_tikz_open(writer, path)
            except Exception as exc:
                self._log_event(
                    f"Could not deliver TikZ open request path={path}: "
                    f"{type(exc).__name__}: {exc}"
                )

    async def _send_tikz_open(self, writer, path: Path) -> None:
        """Send source immediately, then render its preview without blocking editor opening."""
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(self.workspace).as_posix()
        await self._send_tcp(
            writer,
            {
                "type": "open_tikz",
                "path": relative,
                "source": source,
            },
        )
        self._log_event(f"Sent immediate TikZ editor open path={path}")
        self._schedule_tikz_render(writer, path, source)

    def _schedule_tikz_render(self, writer, path: Path, source: str) -> None:
        """Track one non-blocking preview task so shutdown can cancel it cleanly."""
        task = asyncio.create_task(self._render_and_send_tikz_preview(writer, path, source))
        self._tikz_render_tasks.add(task)
        task.add_done_callback(self._tikz_render_tasks.discard)

    async def _send_tikz_render(self, writer, path: Path) -> None:
        """Render the canonical TikZ source on explicit iPad request."""
        source = path.read_text(encoding="utf-8")
        await self._render_and_send_tikz_preview(writer, path, source)

    async def _render_and_send_tikz_preview(
        self,
        writer,
        path: Path,
        source: str,
    ) -> None:
        """Render TikZ off the event loop and return preview or render diagnostics."""
        relative = path.relative_to(self.workspace).as_posix()
        payload: dict[str, Any] = {
            "type": "tikz_rendered",
            "path": relative,
            "source": source,
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

    def _current_tikz_request(self) -> tuple[int, Path] | None:
        """Return the durable TikZ request together with its filesystem revision time."""
        try:
            stat = self.tikz_request_path.stat()
            payload = json.loads(self.tikz_request_path.read_text(encoding="utf-8"))
            path = self._resolve_tikz(str(payload.get("path", "")))
            return stat.st_mtime_ns, path
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _resolve_tikz(self, relative: str) -> Path:
        """Resolve one canonical workspace TikZ source without escaping the workspace."""
        raw = str(relative).strip()
        if not raw:
            raise ValueError("TikZ path is empty")
        path = (self.workspace / raw).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("TikZ path must stay inside the workspace") from exc
        if path.suffix.lower() not in {".tex", ".tikz"} or not path.is_file():
            raise ValueError("TikZ source does not exist")
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "\\begin{tikzpicture}" not in source:
            raise ValueError("Selected file is not a TikZ source")
        return path

    def _tikz_open_request_mtime_ns(self) -> int:
        """Return the durable request mtime, or zero before the first request exists."""
        try:
            return self.tikz_request_path.stat().st_mtime_ns
        except OSError:
            return 0

    @staticmethod
    def _safe_int(value: object) -> int:
        """Coerce client revisions without allowing malformed values to break the bridge."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
