from __future__ import annotations

import argparse

import uvicorn

from .server import GraphicBridgeServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Mind Mirror iPad graphic bridge")
    parser.add_argument("--workspace", default="~/Dropbox/repo")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    server = GraphicBridgeServer(args.workspace, token=args.token)
    uvicorn.run(server.app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
