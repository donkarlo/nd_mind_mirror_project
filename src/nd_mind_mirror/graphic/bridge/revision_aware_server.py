"""Reliable explicit-open delivery layered over the existing revision-aware bridge."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nd_mind_mirror.graphic.bridge.revision_aware_server_base import (
    RevisionAwareGraphicBridgeServer as RevisionAwareGraphicBridgeServerBase,
)
from nd_mind_mirror.graphic.bridge.server_compat import (
    PreservingGraphicBridgeServer,
)
from nd_mind_mirror.graphic.bridge.reverse_tcp_connection_health_policy import (
    ReverseTcpConnectionHealthPolicy,
)


class RevisionAwareGraphicBridgeServer(RevisionAwareGraphicBridgeServerBase):
    """Recover automatically from half-open iPad sockets without losing open requests."""

    _OPEN_DELIVERY_CONFIRM_SECONDS = 5.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._reverse_connection_health = ReverseTcpConnectionHealthPolicy()
        self._delivery_confirmation_tasks: set[asyncio.Task[None]] = set()

    async def shutdown(self) -> None:
        """Cancel pending delivery confirmations before inherited transport shutdown."""
        tasks = tuple(self._delivery_confirmation_tasks)
        self._delivery_confirmation_tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        await super().shutdown()

    async def _broadcast_open(
        self,
        sidecar: Path,
        message_type: str,
        client_revision: int = 0,
        *,
        operation: str | None = None,
    ) -> None:
        """Send the open without declaring success from a stale writer snapshot."""
        await PreservingGraphicBridgeServer._broadcast_open(
            self,
            sidecar,
            message_type,
            client_revision,
            operation=operation,
        )
        if message_type != "open_graphic":
            return

        request = self._current_open_request()
        if request is None:
            return
        request_mtime, request_sidecar, _request_operation = request
        if request_sidecar != sidecar.expanduser().resolve():
            return

        live_writers = tuple(
            writer
            for writer in self.tcp_clients
            if not writer.is_closing()
        )
        if live_writers:
            self._schedule_delivery_confirmation(
                request_mtime,
                request_sidecar,
                live_writers,
            )
            return

        # Browser/WebSocket compatibility has no reverse-TCP liveness channel.
        if self.clients:
            self._mark_open_request_delivered(
                request_mtime,
                request_sidecar,
                transport="WebSocket",
            )

    async def _watch_explicit_open_requests(self) -> None:
        """Send each new durable request once; reconnect handles an unconfirmed send."""
        while True:
            try:
                request = self._current_open_request()
                if request is not None:
                    request_mtime, sidecar, operation = request
                    if request_mtime > self._last_seen_open_request_mtime_ns:
                        self._last_seen_open_request_mtime_ns = request_mtime
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
                                    "Sent explicit iPad open request; "
                                    f"awaiting connection-health confirmation path={sidecar} "
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
        """Resend the newest unconfirmed request after a reverse reconnect."""
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
        self._schedule_delivery_confirmation(
            request_mtime,
            sidecar,
            (writer,),
        )
        self._log_event(
            "Resent pending explicit iPad open request after reconnect "
            f"path={sidecar} operation={operation}"
        )

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        greeting: dict[str, Any],
    ) -> None:
        """Use aggressive TCP liveness and keep pending requests recoverable."""
        version = str(greeting.get("version", "unknown"))
        keepalive = self._reverse_connection_health.configure(writer)
        self._log_event(
            f"Reverse iPad listener discovered at {host}:{self.ipad_listener_port} "
            f"version={version}; keepalive={'enabled' if keepalive else 'unavailable'}"
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

    def _schedule_delivery_confirmation(
        self,
        request_mtime: int,
        sidecar: Path,
        writers: tuple[asyncio.StreamWriter, ...],
    ) -> None:
        """Confirm only after the reverse connection survives the keepalive window."""
        task = asyncio.create_task(
            self._confirm_delivery_after_health_window(
                int(request_mtime),
                sidecar.expanduser().resolve(),
                writers,
            )
        )
        self._delivery_confirmation_tasks.add(task)
        task.add_done_callback(self._delivery_confirmation_tasks.discard)

    async def _confirm_delivery_after_health_window(
        self,
        request_mtime: int,
        sidecar: Path,
        writers: tuple[asyncio.StreamWriter, ...],
    ) -> None:
        await asyncio.sleep(self._OPEN_DELIVERY_CONFIRM_SECONDS)

        request = self._current_open_request()
        if request is None:
            return
        current_mtime, current_sidecar, _operation = request
        if current_mtime != request_mtime or current_sidecar != sidecar:
            return

        if not any(
            writer in self.tcp_clients and not writer.is_closing()
            for writer in writers
        ):
            self._log_event(
                "Open request remains pending because reverse iPad connection "
                f"did not survive health window path={sidecar}"
            )
            return

        self._mark_open_request_delivered(
            request_mtime,
            sidecar,
            transport="reverse TCP",
        )

    def _mark_open_request_delivered(
        self,
        request_mtime: int,
        sidecar: Path,
        *,
        transport: str,
    ) -> None:
        self._last_delivered_open_request_mtime_ns = max(
            self._last_delivered_open_request_mtime_ns,
            int(request_mtime),
        )
        self._log_event(
            f"Confirmed iPad open delivery via {transport} path={sidecar}"
        )
