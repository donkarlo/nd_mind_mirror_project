"""Application-level liveness monitor for the reverse Ubuntu-to-iPad TCP connection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class ReverseTcpHeartbeatMonitor:
    """Require a real iPad application response so suspended sockets cannot look healthy."""

    _PROBE_INTERVAL_SECONDS = 2.0
    _PONG_TIMEOUT_SECONDS = 4.0

    def __init__(
        self,
        writer: asyncio.StreamWriter,
        send_payload: Callable[[asyncio.StreamWriter, dict[str, Any]], Awaitable[None]],
        on_timeout: Callable[[asyncio.StreamWriter, str], Awaitable[None]],
    ) -> None:
        self._writer = writer
        self._send_payload = send_payload
        self._on_timeout = on_timeout
        self._pong_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start one heartbeat loop for this concrete reverse connection."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the heartbeat without treating an intentional shutdown as a timeout."""
        task = self._task
        self._task = None
        if task is None or task is asyncio.current_task() or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def acknowledge(self) -> None:
        """Record a pong emitted by the iPad application, not merely by the TCP stack."""
        self._pong_event.set()

    async def _run(self) -> None:
        try:
            while not self._writer.is_closing():
                await asyncio.sleep(self._PROBE_INTERVAL_SECONDS)
                if self._writer.is_closing():
                    return

                self._pong_event.clear()
                try:
                    await self._send_payload(
                        self._writer,
                        {"type": "heartbeat_ping"},
                    )
                except (ConnectionError, BrokenPipeError, OSError) as exc:
                    await self._on_timeout(
                        self._writer,
                        f"heartbeat send failed: {type(exc).__name__}",
                    )
                    return

                try:
                    await asyncio.wait_for(
                        self._pong_event.wait(),
                        timeout=self._PONG_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    await self._on_timeout(
                        self._writer,
                        "no iPad application heartbeat_pong",
                    )
                    return
        except asyncio.CancelledError:
            raise
