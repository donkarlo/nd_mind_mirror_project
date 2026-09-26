"""Reliable explicit-open delivery layered over the existing revision-aware bridge."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
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
from nd_mind_mirror.graphic.bridge.reverse_tcp_heartbeat_monitor import (
    ReverseTcpHeartbeatMonitor,
)


class RevisionAwareGraphicBridgeServer(RevisionAwareGraphicBridgeServerBase):
    """Recover automatically from stale iPad sockets and require app-level open ACKs."""

    _OPEN_DELIVERY_ACK_TIMEOUT_SECONDS = 5.0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._reverse_connection_health = ReverseTcpConnectionHealthPolicy()
        self._reverse_heartbeat_monitors: dict[
            asyncio.StreamWriter,
            ReverseTcpHeartbeatMonitor,
        ] = {}
        self._open_delivery_sequence = 0
        self._pending_open_delivery_id: str | None = None
        self._pending_open_request_mtime_ns = 0
        self._pending_open_sidecar: Path | None = None
        self._pending_open_writers: tuple[asyncio.StreamWriter, ...] = ()
        self._open_ack_timeout_task: asyncio.Task[None] | None = None
        self._outbound_open_delivery_id: ContextVar[str | None] = ContextVar(
            f"nd_graphic_open_delivery_id_{id(self)}",
            default=None,
        )

    async def shutdown(self) -> None:
        """Stop application heartbeats and the open ACK timeout before transport shutdown."""
        heartbeats = tuple(self._reverse_heartbeat_monitors.values())
        self._reverse_heartbeat_monitors.clear()
        for heartbeat in heartbeats:
            await heartbeat.stop()
        self._clear_pending_open_delivery()
        await super().shutdown()

    def _open_payload(
        self,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
        client_revision: int = 0,
    ) -> dict[str, Any]:
        """Attach the per-attempt delivery id only to explicit raster open messages."""
        payload = super()._open_payload(
            sidecar,
            message_type,
            operation=operation,
            client_revision=client_revision,
        )
        delivery_id = self._outbound_open_delivery_id.get()
        if message_type == "open_graphic" and delivery_id:
            payload["delivery_id"] = delivery_id
        return payload

    async def _broadcast_open(
        self,
        sidecar: Path,
        message_type: str,
        client_revision: int = 0,
        *,
        operation: str | None = None,
    ) -> None:
        """Send an explicit open once and wait for the iPad application ACK."""
        if message_type != "open_graphic":
            await PreservingGraphicBridgeServer._broadcast_open(
                self,
                sidecar,
                message_type,
                client_revision,
                operation=operation,
            )
            return

        request = self._matching_open_request(sidecar)
        live_writers = tuple(
            writer for writer in self.tcp_clients if not writer.is_closing()
        )

        if request is not None and live_writers:
            request_mtime, request_sidecar, _request_operation = request
            if self._is_open_delivery_pending(request_mtime, request_sidecar):
                self._log_event(
                    "Coalesced duplicate explicit iPad open while ACK is pending "
                    f"path={request_sidecar}"
                )
                return

            delivery_id = self._prepare_open_delivery(
                request_mtime,
                request_sidecar,
                live_writers,
            )
            token = self._outbound_open_delivery_id.set(delivery_id)
            try:
                await PreservingGraphicBridgeServer._broadcast_open(
                    self,
                    sidecar,
                    message_type,
                    client_revision,
                    operation=operation,
                )
            finally:
                self._outbound_open_delivery_id.reset(token)
            self._arm_open_ack_timeout(delivery_id)
            return

        await PreservingGraphicBridgeServer._broadcast_open(
            self,
            sidecar,
            message_type,
            client_revision,
            operation=operation,
        )

        # Browser/WebSocket compatibility has no native iPad ACK channel.
        if request is not None and self.clients and not live_writers:
            request_mtime, request_sidecar, _request_operation = request
            self._mark_open_request_delivered(
                request_mtime,
                request_sidecar,
                transport="WebSocket",
            )

    async def _send_open_tcp(
        self,
        writer: asyncio.StreamWriter,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
    ) -> None:
        """Send a single-client explicit open with an application ACK id."""
        request = self._matching_open_request(sidecar)
        if (
            message_type != "open_graphic"
            or request is None
            or request[0] <= self._last_delivered_open_request_mtime_ns
        ):
            await super()._send_open_tcp(
                writer,
                sidecar,
                message_type,
                operation=operation,
            )
            return

        request_mtime, request_sidecar, _request_operation = request
        delivery_id = self._prepare_open_delivery(
            request_mtime,
            request_sidecar,
            (writer,),
        )
        token = self._outbound_open_delivery_id.set(delivery_id)
        try:
            await super()._send_open_tcp(
                writer,
                sidecar,
                message_type,
                operation=operation,
            )
        finally:
            self._outbound_open_delivery_id.reset(token)
        self._arm_open_ack_timeout(delivery_id)

    async def _watch_explicit_open_requests(self) -> None:
        """Deliver each durable request once; retry only after ACK failure/reconnect."""
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
                            if self._is_open_delivery_pending(request_mtime, sidecar):
                                pass
                            elif self.tcp_clients or self.clients:
                                await self._broadcast_open(
                                    sidecar,
                                    "open_graphic",
                                    operation=operation,
                                )
                                self._log_event(
                                    "Sent explicit iPad open request; awaiting application ACK "
                                    f"path={sidecar} operation={operation}"
                                )
                            else:
                                self._log_event(
                                    "Queued explicit iPad open request until connection "
                                    f"path={sidecar} operation={operation}"
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
        """Resend the newest unacknowledged request after a reverse reconnect."""
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
        self._log_event(
            "Resent pending explicit iPad open request after reconnect; awaiting ACK "
            f"path={sidecar} operation={operation}"
        )

    async def _deliver_pending_reverse_request(self, writer) -> None:
        """Deliver the pending request selected by the active server specialization."""
        await self._deliver_pending_open_request(writer)

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        greeting: dict[str, Any],
    ) -> None:
        """Keep one reverse connection only while the iPad application itself is responsive."""
        version = str(greeting.get("version", "unknown"))
        keepalive = self._reverse_connection_health.configure(writer)
        self._log_event(
            f"Reverse iPad listener discovered at {host}:{self.ipad_listener_port} "
            f"version={version}; keepalive={'enabled' if keepalive else 'unavailable'}"
        )
        self.tcp_clients.add(writer)

        heartbeat: ReverseTcpHeartbeatMonitor | None = None
        raw_capabilities = greeting.get("capabilities", [])
        capabilities = {
            str(value)
            for value in raw_capabilities
            if isinstance(raw_capabilities, list)
        }
        if "heartbeat_pong" in capabilities:
            heartbeat = ReverseTcpHeartbeatMonitor(
                writer,
                self._send_tcp,
                self._drop_stale_reverse_connection,
            )
            self._reverse_heartbeat_monitors[writer] = heartbeat
        else:
            self._log_event(
                "Reverse iPad client does not advertise application heartbeat; "
                f"version={version}"
            )

        try:
            await self._send_tcp(writer, {"type": "hello", "version": self.app.version})
            await self._deliver_pending_reverse_request(writer)
            if heartbeat is not None:
                heartbeat.start()
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
            registered_heartbeat = self._reverse_heartbeat_monitors.pop(writer, None)
            if registered_heartbeat is not None:
                await registered_heartbeat.stop()
            self.tcp_clients.discard(writer)
            self._drop_pending_delivery_for_writer(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _drop_stale_reverse_connection(
        self,
        writer: asyncio.StreamWriter,
        reason: str,
    ) -> None:
        """Release a suspended iPad socket immediately so LAN discovery can run again."""
        if writer not in self.tcp_clients:
            return

        self._log_event(
            "iPad application heartbeat timed out; dropping stale connection "
            f"reason={reason}"
        )
        self.tcp_clients.discard(writer)
        self._drop_pending_delivery_for_writer(writer)
        if not writer.is_closing():
            writer.close()

    async def _handle_tcp(
        self,
        writer: asyncio.StreamWriter,
        payload: dict[str, Any],
    ) -> None:
        """Consume liveness/open ACKs before normal bridge message routing."""
        message_type = str(payload.get("type", ""))
        if message_type == "heartbeat_pong":
            monitor = self._reverse_heartbeat_monitors.get(writer)
            if monitor is not None:
                monitor.acknowledge()
            return
        if message_type == "open_graphic_ack":
            self._accept_open_graphic_ack(payload)
            return
        await super()._handle_tcp(writer, payload)

    def _matching_open_request(
        self,
        sidecar: Path,
    ) -> tuple[int, Path, str] | None:
        request = self._current_open_request()
        if request is None:
            return None
        request_mtime, request_sidecar, operation = request
        if request_sidecar != sidecar.expanduser().resolve():
            return None
        return request_mtime, request_sidecar, operation

    def _is_open_delivery_pending(self, request_mtime: int, sidecar: Path) -> bool:
        return (
            self._pending_open_delivery_id is not None
            and self._pending_open_request_mtime_ns == int(request_mtime)
            and self._pending_open_sidecar == sidecar.expanduser().resolve()
        )

    def _prepare_open_delivery(
        self,
        request_mtime: int,
        sidecar: Path,
        writers: tuple[asyncio.StreamWriter, ...],
    ) -> str:
        """Create one unique ACK id for one concrete transport attempt."""
        self._clear_pending_open_delivery()
        self._open_delivery_sequence += 1
        delivery_id = f"{int(request_mtime):x}-{self._open_delivery_sequence:x}"
        self._pending_open_delivery_id = delivery_id
        self._pending_open_request_mtime_ns = int(request_mtime)
        self._pending_open_sidecar = sidecar.expanduser().resolve()
        self._pending_open_writers = writers
        return delivery_id

    def _arm_open_ack_timeout(self, delivery_id: str) -> None:
        """Start the ACK deadline only after the complete open payload was written."""
        if self._pending_open_delivery_id != delivery_id:
            return
        task = asyncio.create_task(self._expire_open_delivery(delivery_id))
        self._open_ack_timeout_task = task

    async def _expire_open_delivery(self, delivery_id: str) -> None:
        await asyncio.sleep(self._OPEN_DELIVERY_ACK_TIMEOUT_SECONDS)
        if self._pending_open_delivery_id != delivery_id:
            return

        sidecar = self._pending_open_sidecar
        writers = self._pending_open_writers
        self._log_event(
            "iPad open ACK timeout; dropping stale reverse connection and retrying "
            f"path={sidecar} delivery_id={delivery_id}"
        )
        self._clear_pending_open_delivery(cancel_timeout=False)

        for writer in writers:
            self.tcp_clients.discard(writer)
            if not writer.is_closing():
                writer.close()

    def _accept_open_graphic_ack(self, payload: dict[str, Any]) -> None:
        """Mark delivery only when the iPad confirms it applied this exact open."""
        delivery_id = str(payload.get("delivery_id", "") or "")
        if not delivery_id or delivery_id != self._pending_open_delivery_id:
            self._log_event(
                f"Ignored stale or unknown iPad open ACK delivery_id={delivery_id or '-'}"
            )
            return

        request_mtime = self._pending_open_request_mtime_ns
        sidecar = self._pending_open_sidecar
        if request_mtime <= 0 or sidecar is None:
            self._clear_pending_open_delivery()
            return

        self._clear_pending_open_delivery()
        self._mark_open_request_delivered(
            request_mtime,
            sidecar,
            transport="reverse TCP application ACK",
        )

    def _drop_pending_delivery_for_writer(self, writer: asyncio.StreamWriter) -> None:
        """Keep the durable request pending when its transport disappears."""
        if writer not in self._pending_open_writers:
            return
        sidecar = self._pending_open_sidecar
        self._clear_pending_open_delivery()
        self._log_event(
            "Open request remains pending because reverse iPad transport closed "
            f"before application ACK path={sidecar}"
        )

    def _clear_pending_open_delivery(self, *, cancel_timeout: bool = True) -> None:
        task = self._open_ack_timeout_task
        self._open_ack_timeout_task = None
        if (
            cancel_timeout
            and task is not None
            and task is not asyncio.current_task()
            and not task.done()
        ):
            task.cancel()
        self._pending_open_delivery_id = None
        self._pending_open_request_mtime_ns = 0
        self._pending_open_sidecar = None
        self._pending_open_writers = ()

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
