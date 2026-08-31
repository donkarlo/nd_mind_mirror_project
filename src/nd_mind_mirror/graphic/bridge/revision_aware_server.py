"""Revision-aware bridge behavior that suppresses delayed filesystem echoes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import Any

from .server_compat import PreservingGraphicBridgeServer


class RevisionAwareGraphicBridgeServer(PreservingGraphicBridgeServer):
    """Keep iPad saves stable and deliver every explicit desktop open request exactly once."""

    _LOCAL_ECHO_SUPPRESSION_SECONDS = 12.0
    _OPEN_REQUEST_POLL_SECONDS = 0.15

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._explicit_open_request_task: asyncio.Task[None] | None = None
        self._last_seen_open_request_mtime_ns = 0
        self._last_delivered_open_request_mtime_ns = 0

    async def startup(self) -> None:
        # Existing request files are historical state, not a reason to reopen a
        # document when the iPad app starts. Only changes after this startup are
        # considered explicit user requests.
        initial_mtime = self._open_request_mtime_ns()
        self._last_seen_open_request_mtime_ns = initial_mtime
        self._last_delivered_open_request_mtime_ns = initial_mtime
        await super().startup()
        self._explicit_open_request_task = asyncio.create_task(
            self._watch_explicit_open_requests()
        )

    async def shutdown(self) -> None:
        if self._explicit_open_request_task is not None:
            self._explicit_open_request_task.cancel()
            try:
                await self._explicit_open_request_task
            except asyncio.CancelledError:
                pass
            self._explicit_open_request_task = None
        await super().shutdown()

    async def _update_graphic(
        self,
        sidecar: Path,
        payload: dict[str, Any],
    ) -> tuple[Path, int]:
        image_path, revision = await super()._update_graphic(sidecar, payload)
        suppress_until = time.monotonic() + self._LOCAL_ECHO_SUPPRESSION_SECONDS
        self._suppress_broadcast_until[sidecar.expanduser().resolve()] = suppress_until
        if image_path:
            self._suppress_broadcast_until[image_path.expanduser().resolve()] = suppress_until
        return image_path, revision

    async def _handle_tcp(self, writer, payload: dict[str, Any]) -> None:
        # Never ask the server for an arbitrary previous document. Desktop open
        # requests are tracked separately and delivered explicitly.
        if str(payload.get("type", "")) == "request_current":
            return
        await super()._handle_tcp(writer, payload)

    async def _broadcast_open(
        self,
        sidecar: Path,
        message_type: str,
        client_revision: int = 0,
        *,
        operation: str | None = None,
    ) -> None:
        had_receiver = bool(self.tcp_clients or self.clients)
        await super()._broadcast_open(
            sidecar,
            message_type,
            client_revision,
            operation=operation,
        )
        if not had_receiver or message_type != "open_graphic":
            return
        request = self._current_open_request()
        if request is None:
            return
        request_mtime, request_sidecar, _request_operation = request
        if request_sidecar == sidecar.expanduser().resolve():
            self._last_delivered_open_request_mtime_ns = max(
                self._last_delivered_open_request_mtime_ns,
                request_mtime,
            )

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        greeting: dict[str, Any],
    ) -> None:
        """Connect transport and deliver only a still-pending explicit open request."""
        version = str(greeting.get("version", "unknown"))
        self._log_event(
            f"Reverse iPad listener discovered at {host}:{self.ipad_listener_port} "
            f"version={version}; waiting for an explicit Edit image in iPad request"
        )
        self.tcp_clients.add(writer)
        try:
            await self._send_tcp(writer, {"type": "hello", "version": self.app.version})
            await self._deliver_pending_open_request(writer)
            while True:
                payload = await self._read_tcp_json(reader)
                await self._handle_tcp(writer, payload)
        except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError) as exc:
            self._log_event(
                f"Reverse iPad connection closed {host}:{self.ipad_listener_port}: {type(exc).__name__}"
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

    async def _watch_explicit_open_requests(self) -> None:
        """Deliver repeated same-path desktop open requests that the base watcher deduplicates."""
        while True:
            try:
                request = self._current_open_request()
                if request is not None:
                    request_mtime, sidecar, operation = request
                    if request_mtime > self._last_seen_open_request_mtime_ns:
                        self._last_seen_open_request_mtime_ns = request_mtime
                        # Give the normal workspace watcher a chance to deliver a
                        # new-path request. If it did, _broadcast_open records it.
                        await asyncio.sleep(self._OPEN_REQUEST_POLL_SECONDS)
                        if request_mtime > self._last_delivered_open_request_mtime_ns:
                            self.current_sidecar = sidecar
                            self.current_operation = operation
                            if self.tcp_clients or self.clients:
                                await self._broadcast_open(
                                    sidecar,
                                    "open_graphic",
                                    operation=operation,
                                )
                                self._log_event(
                                    f"Delivered explicit iPad open request path={sidecar} "
                                    f"operation={operation}"
                                )
                            else:
                                self._log_event(
                                    f"Queued explicit iPad open request until connection path={sidecar} "
                                    f"operation={operation}"
                                )
                await asyncio.sleep(self._OPEN_REQUEST_POLL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_event(
                    f"Explicit iPad open request watcher error: {type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(0.5)

    async def _deliver_pending_open_request(self, writer) -> None:
        request = self._current_open_request()
        if request is None:
            return
        request_mtime, sidecar, operation = request
        if request_mtime <= self._last_delivered_open_request_mtime_ns:
            return
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
        self._log_event(
            f"Delivered pending explicit iPad open request path={sidecar} operation={operation}"
        )

    def _current_open_request(self) -> tuple[int, Path, str] | None:
        try:
            stat = self.request_path.stat()
            payload = json.loads(self.request_path.read_text(encoding="utf-8"))
            sidecar = self._resolve_sidecar(str(payload.get("path", "")))
            operation = self._normalize_operation(payload.get("operation", "update"))
            return stat.st_mtime_ns, sidecar.expanduser().resolve(), operation
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _open_request_mtime_ns(self) -> int:
        try:
            return self.request_path.stat().st_mtime_ns
        except OSError:
            return 0
