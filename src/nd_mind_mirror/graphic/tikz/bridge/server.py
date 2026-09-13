"""FastAPI WebSocket server for live iPad TikZ editing."""

from __future__ import annotations

from pathlib import Path
import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from watchfiles import awatch

from .renderer import TikZRenderer
from .workspace import TikZWorkspace
from . import __version__


class TikZBridgeServer:
    """Own canonical TikZ files while the iPad edits source over WebSocket."""

    def __init__(self, workspace: TikZWorkspace, renderer: TikZRenderer) -> None:
        self.workspace = workspace
        self.renderer = renderer
        self.clients: set[WebSocket] = set()
        self.last_hash: dict[str, str] = {}
        self.app = FastAPI(title="nd_mind_mirror_tikz_bridge", version=__version__)
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.app.post("/desktop/open")(self.desktop_open)
        self.app.on_event("startup")(self.startup)

    async def startup(self) -> None:
        """Start watching external source changes after the bridge starts."""
        asyncio.create_task(self._watch_workspace())

    async def desktop_open(self, payload: dict[str, Any]) -> dict[str, str]:
        """Forward a desktop Create/Edit request to every connected iPad client."""
        relative = str(payload.get("path", "")).strip()
        if not relative:
            raise ValueError("TikZ path is required")
        source = self.workspace.read(relative)
        if "\\begin{tikzpicture}" not in source:
            raise ValueError(f"Not a TikZ source: {relative}")
        await self._broadcast({"type": "desktop_open", "path": relative})
        return {"status": "ok", "path": relative}

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        """Serve one iPad client until disconnect."""
        await websocket.accept()
        self.clients.add(websocket)
        await self._send(websocket, {"type": "hello", "version": __version__})
        try:
            while True:
                await self._handle(websocket, await websocket.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            self.clients.discard(websocket)

    async def _handle(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        """Dispatch bridge messages without mixing TikZ with raster-image protocol."""
        message_type = str(payload.get("type", ""))
        try:
            if message_type == "list_files":
                await self._send(
                    websocket,
                    {"type": "file_list", "files": self.workspace.list_files()},
                )
            elif message_type == "open_file":
                await self._open_file(websocket, str(payload["path"]))
            elif message_type == "update_source":
                await self._update_source(
                    str(payload["path"]),
                    str(payload.get("source", "")),
                    int(payload.get("client_revision", 0)),
                )
            elif message_type == "render":
                await self._render_and_send(websocket, str(payload["path"]))
            else:
                await self._send(
                    websocket,
                    {"type": "error", "message": f"Unknown message type: {message_type}"},
                )
        except (OSError, ValueError, KeyError) as exc:
            await self._send(websocket, {"type": "error", "message": str(exc)})

    async def _open_file(self, websocket: WebSocket, relative: str) -> None:
        """Read and render one requested source file."""
        source = self.workspace.read(relative)
        self.last_hash[relative] = self.workspace.digest(relative)
        payload: dict[str, Any] = {
            "type": "file_opened",
            "path": relative,
            "source": source,
        }
        try:
            result = await asyncio.to_thread(
                self.renderer.render,
                source,
                self.workspace.resolve_relative(relative),
            )
            payload["preview_png_base64"] = result.png_base64
        except Exception as exc:
            payload["message"] = str(exc)
        await self._send(websocket, payload)

    async def _update_source(
        self,
        relative: str,
        source: str,
        client_revision: int,
    ) -> None:
        """Atomically save one iPad source revision and broadcast its fresh render."""
        path = self.workspace.write_atomic(relative, source)
        self.last_hash[relative] = self.workspace.digest(relative)
        try:
            result = await asyncio.to_thread(self.renderer.render, source, path)
        except Exception as exc:
            await self._broadcast(
                {
                    "type": "render_error",
                    "path": relative,
                    "source": source,
                    "client_revision": client_revision,
                    "message": str(exc),
                }
            )
            return
        await self._broadcast(
            {
                "type": "file_updated",
                "path": relative,
                "source": source,
                "preview_png_base64": result.png_base64,
                "client_revision": client_revision,
            }
        )

    async def _render_and_send(self, websocket: WebSocket, relative: str) -> None:
        """Render the current canonical file without changing it."""
        source = self.workspace.read(relative)
        result = await asyncio.to_thread(
            self.renderer.render,
            source,
            self.workspace.resolve_relative(relative),
        )
        await self._send(
            websocket,
            {
                "type": "rendered",
                "path": relative,
                "source": source,
                "preview_png_base64": result.png_base64,
            },
        )

    async def _watch_workspace(self) -> None:
        """Reflect external editor changes back to connected iPads."""
        async for changes in awatch(self.workspace.root, debounce=250):
            for _, changed_raw in changes:
                path = Path(changed_raw)
                if not path.is_file() or path.suffix.lower() not in {".tikz", ".tex"}:
                    continue
                try:
                    relative = path.resolve().relative_to(self.workspace.root).as_posix()
                    if path.suffix.lower() == ".tex" and "\\begin{tikzpicture}" not in path.read_text(encoding="utf-8", errors="ignore"):
                        continue
                    digest = self.workspace.digest(relative)
                    if self.last_hash.get(relative) == digest:
                        continue
                    self.last_hash[relative] = digest
                    source = self.workspace.read(relative)
                    result = await asyncio.to_thread(self.renderer.render, source, path.resolve())
                    await self._broadcast(
                        {
                            "type": "external_change",
                            "path": relative,
                            "source": source,
                            "preview_png_base64": result.png_base64,
                        }
                    )
                except Exception as exc:
                    await self._broadcast(
                        {"type": "render_error", "path": relative, "message": str(exc)}
                    )

    @staticmethod
    async def _send(websocket: WebSocket, payload: dict[str, Any]) -> None:
        """Send one UTF-8 JSON message."""
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast one message and forget disconnected clients."""
        text = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for client in tuple(self.clients):
            try:
                await client.send_text(text)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)
