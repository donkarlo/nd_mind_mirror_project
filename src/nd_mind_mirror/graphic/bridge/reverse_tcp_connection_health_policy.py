"""TCP liveness policy for the reverse Ubuntu-to-iPad graphic connection."""

from __future__ import annotations

import socket


class ReverseTcpConnectionHealthPolicy:
    """Configure aggressive LAN keepalive so half-open iPad sockets die promptly."""

    _KEEP_IDLE_SECONDS = 2
    _KEEP_INTERVAL_SECONDS = 1
    _KEEP_PROBE_COUNT = 3
    _USER_TIMEOUT_MS = 4000

    def configure(self, writer) -> bool:
        """Apply Linux TCP liveness options to one established reverse connection."""
        raw_socket = writer.get_extra_info("socket")
        if raw_socket is None:
            return False

        try:
            raw_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_KEEPALIVE,
                1,
            )
            self._set_optional(
                raw_socket,
                "TCP_KEEPIDLE",
                self._KEEP_IDLE_SECONDS,
            )
            self._set_optional(
                raw_socket,
                "TCP_KEEPINTVL",
                self._KEEP_INTERVAL_SECONDS,
            )
            self._set_optional(
                raw_socket,
                "TCP_KEEPCNT",
                self._KEEP_PROBE_COUNT,
            )
            self._set_optional(
                raw_socket,
                "TCP_USER_TIMEOUT",
                self._USER_TIMEOUT_MS,
            )
            return True
        except OSError:
            return False

    @staticmethod
    def _set_optional(raw_socket, option_name: str, value: int) -> None:
        option = getattr(socket, option_name, None)
        if option is None:
            return
        raw_socket.setsockopt(socket.IPPROTO_TCP, option, int(value))
