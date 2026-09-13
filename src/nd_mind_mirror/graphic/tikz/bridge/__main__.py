"""Command-line entry point for the active Mind Mirror TikZ bridge."""

from __future__ import annotations

import argparse

import uvicorn

from .renderer import TikZRenderer
from .server import TikZBridgeServer
from .workspace import TikZWorkspace


def build_parser() -> argparse.ArgumentParser:
    """Build bridge CLI arguments."""
    parser = argparse.ArgumentParser(description="Mind Mirror iPad TikZ bridge")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> None:
    """Run the TikZ bridge for one Mind Mirror workspace."""
    args = build_parser().parse_args()
    workspace = TikZWorkspace(args.workspace)
    renderer = TikZRenderer(workspace.root)
    server = TikZBridgeServer(workspace, renderer)
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
