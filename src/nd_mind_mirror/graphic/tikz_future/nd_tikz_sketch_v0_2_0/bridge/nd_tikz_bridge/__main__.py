from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .renderer import TikZRenderer
from .server import BridgeServer
from .workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live iPad ↔ Ubuntu TikZ bridge")
    parser.add_argument("--workspace", required=True, help="Workspace root, e.g. ~/Dropbox/repo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default="", help="Optional shared token")
    parser.add_argument("--preamble", default="", help="Optional LaTeX preamble fragment for standalone TikZ rendering")
    parser.add_argument("--shell-escape", action="store_true")
    parser.add_argument("--extensions", default=".tikz,.tex")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    extensions = tuple(
        item if item.startswith(".") else "." + item
        for item in (part.strip() for part in args.extensions.split(","))
        if item
    )
    workspace = Workspace(args.workspace, extensions=extensions)
    preamble = Path(args.preamble).expanduser() if args.preamble else None
    renderer = TikZRenderer(
        workspace=workspace.root,
        preamble_path=preamble,
        shell_escape=args.shell_escape,
    )
    server = BridgeServer(workspace, renderer, token=args.token)
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
