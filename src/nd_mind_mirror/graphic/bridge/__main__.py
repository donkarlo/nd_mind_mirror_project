"""Launch the graphic bridge with collision-safe local transport ports."""

from __future__ import annotations

import argparse
import socket

import uvicorn

from .server_compat import PreservingGraphicBridgeServer


def _port_is_available(host: str, port: int) -> bool:
    """Return whether a TCP listener can bind to the requested local address."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _next_available_port(host: str, start: int, reserved: set[int]) -> int:
    """Find the first bindable TCP port at or above start, excluding reserved ports."""
    for candidate in range(start, 65536):
        if candidate in reserved:
            continue
        if _port_is_available(host, candidate):
            return candidate
    raise RuntimeError(f"No free TCP port available at or above {start}")


def main() -> int:
    """Parse bridge settings, resolve port collisions, and run the server."""
    parser = argparse.ArgumentParser(description="Mind Mirror iPad graphic bridge")
    parser.add_argument("--workspace", default="~/Dropbox/repo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766, help="HTTP/WebSocket port")
    parser.add_argument("--tcp-port", type=int, default=8767, help="Legacy iPad direct TCP port")
    parser.add_argument("--ipad-listen-port", type=int, default=8768, help="Port listened to by ND Graphic on iPad")
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    requested_port = args.port
    requested_tcp_port = args.tcp_port
    websocket_reserved = {args.ipad_listen_port}
    if args.tcp_port != args.port:
        websocket_reserved.add(args.tcp_port)
    args.port = _next_available_port(args.host, args.port, websocket_reserved)
    args.tcp_port = _next_available_port(
        args.host,
        args.tcp_port,
        {args.ipad_listen_port, args.port},
    )

    if args.port != requested_port:
        print(f"[ND Graphic] WebSocket port {requested_port} busy; using {args.port}", flush=True)
    if args.tcp_port != requested_tcp_port:
        print(f"[ND Graphic] Legacy TCP port {requested_tcp_port} busy; using {args.tcp_port}", flush=True)

    server = PreservingGraphicBridgeServer(
        args.workspace,
        token=args.token,
        tcp_host=args.host,
        tcp_port=args.tcp_port,
        ipad_listener_port=args.ipad_listen_port,
    )
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
