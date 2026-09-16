"""Launch the unified image/TikZ bridge on one deterministic port set."""

from __future__ import annotations

import argparse
import socket

import uvicorn

from .configured_unified_server import ConfiguredUnifiedGraphicBridgeServer


def _port_is_available(host: str, port: int) -> bool:
    """Return whether one requested listener can bind before server startup."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def _validate_ports(
    host: str,
    websocket_port: int,
    tcp_port: int,
    ipad_listener_port: int,
) -> None:
    """Reject duplicate/busy ports instead of creating competing bridge instances."""
    ports = {
        "websocket": websocket_port,
        "legacy TCP": tcp_port,
        "iPad listener": ipad_listener_port,
    }
    if len(set(ports.values())) != len(ports):
        raise SystemExit(f"ND Graphic bridge ports must be distinct: {ports}")

    for label, port in (
        ("websocket", websocket_port),
        ("legacy TCP", tcp_port),
    ):
        if not _port_is_available(host, port):
            raise SystemExit(
                f"ND Graphic {label} port {port} is already in use. "
                "Fallback ports are disabled to prevent multiple bridges "
                "from fighting for the iPad connection."
            )


def main() -> int:
    """Parse bridge settings and run exactly on the requested transport ports."""
    parser = argparse.ArgumentParser(
        description="Mind Mirror iPad graphic bridge"
    )
    parser.add_argument("--workspace", default="~/Dropbox/repo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument(
        "--port",
        type=int,
        default=8766,
        help="HTTP/WebSocket port",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=8767,
        help="Legacy iPad direct TCP port",
    )
    parser.add_argument(
        "--ipad-listen-port",
        type=int,
        default=8768,
        help="Port listened to by ND Graphic on iPad",
    )
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    _validate_ports(
        args.host,
        args.port,
        args.tcp_port,
        args.ipad_listen_port,
    )

    server = ConfiguredUnifiedGraphicBridgeServer(
        args.workspace,
        token=args.token,
        tcp_host=args.host,
        tcp_port=args.tcp_port,
        ipad_listener_port=args.ipad_listen_port,
    )
    uvicorn.run(
        server.app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
