from __future__ import annotations

from pathlib import Path
import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from watchfiles import awatch

from .renderer import TikZRenderer
from .workspace import Workspace
from . import __version__


class BridgeServer:
    def __init__(
        self,
        workspace: Workspace,
        renderer: TikZRenderer,
        token: str = "",
    ) -> None:
        self.workspace = workspace
        self.renderer = renderer
        self.token = token
        self.clients: set[WebSocket] = set()
        self.last_hash: dict[str, str] = {}
        self.app = FastAPI(title="nd_tikz_bridge", version=__version__)
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.app.on_event("startup")(self.startup)

    async def startup(self) -> None:
        asyncio.create_task(self._watch_workspace())

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        if self.token and websocket.query_params.get("token", "") != self.token:
            await websocket.close(code=1008, reason="Invalid token")
            return
        await websocket.accept()
        self.clients.add(websocket)
        await self._send(websocket, {"type": "hello", "version": __version__})
        try:
            while True:
                payload = await websocket.receive_json()
                await self._handle(websocket, payload)
        except WebSocketDisconnect:
            pass
        finally:
            self.clients.discard(websocket)

    async def _handle(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        message_type = str(payload.get("type", ""))
        try:
            if message_type == "list_files":
                await self._send(websocket, {"type": "file_list", "files": self.workspace.list_files()})
                return
            if message_type == "open_file":
                await self._open_file(websocket, str(payload["path"]))
                return
            if message_type == "update_source":
                await self._update_source(
                    websocket,
                    str(payload["path"]),
                    str(payload.get("source", "")),
                    int(payload.get("client_revision", 0)),
                )
                return
            if message_type == "render":
                await self._render_and_send(websocket, str(payload["path"]), "rendered", 0)
                return
            await self._send(websocket, {"type": "error", "message": f"Unknown message type: {message_type}"})
        except (OSError, ValueError, KeyError) as exc:
            await self._send(websocket, {"type": "error", "message": str(exc)})

    async def _open_file(self, websocket: WebSocket, relative: str) -> None:
        source = self.workspace.read(relative)
        self.last_hash[relative] = self.workspace.digest(relative)
        try:
            result = await asyncio.to_thread(
                self.renderer.render,
                source,
                self.workspace.resolve_relative(relative),
            )
            preview = result.png_base64
            message = None
        except Exception as exc:  # render diagnostics must reach the iPad
            preview = None
            message = str(exc)
        payload: dict[str, Any] = {
            "type": "file_opened",
            "path": relative,
            "source": source,
            "preview_png_base64": preview,
        }
        if message:
            payload["message"] = message
        await self._send(websocket, payload)

    async def _update_source(
        self,
        websocket: WebSocket,
        relative: str,
        source: str,
        client_revision: int,
    ) -> None:
        path = self.workspace.write_atomic(relative, source)
        self.last_hash[relative] = self.workspace.digest(relative)
        try:
            result = await asyncio.to_thread(self.renderer.render, source, path)
        except Exception as exc:
            await self._send(
                websocket,
                {
                    "type": "render_error",
                    "path": relative,
                    "source": source,
                    "client_revision": client_revision,
                    "message": str(exc),
                },
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

    async def _render_and_send(
        self,
        websocket: WebSocket,
        relative: str,
        response_type: str,
        client_revision: int,
    ) -> None:
        source = self.workspace.read(relative)
        result = await asyncio.to_thread(
            self.renderer.render,
            source,
            self.workspace.resolve_relative(relative),
        )
        await self._send(
            websocket,
            {
                "type": response_type,
                "path": relative,
                "source": source,
                "preview_png_base64": result.png_base64,
                "client_revision": client_revision,
            },
        )

    async def _watch_workspace(self) -> None:
        async for changes in awatch(self.workspace.root, debounce=250):
            for _, changed_raw in changes:
                path = Path(changed_raw)
                if not path.is_file() or path.suffix.lower() not in self.workspace.extensions:
                    continue
                try:
                    relative = path.resolve().relative_to(self.workspace.root).as_posix()
                    digest = self.workspace.digest(relative)
                except (OSError, ValueError):
                    continue
                if self.last_hash.get(relative) == digest:
                    continue
                self.last_hash[relative] = digest
                try:
                    source = self.workspace.read(relative)
                    result = await asyncio.to_thread(self.renderer.render, source, path.resolve())
                    await self._broadcast(
                        {
                            "type": "external_change",
                            "path": relative,
                            "source": source,
                            "preview_png_base64": result.png_base64,
                            "client_revision": 0,
                        }
                    )
                except Exception as exc:
                    await self._broadcast(
                        {
                            "type": "render_error",
                            "path": relative,
                            "message": str(exc),
                        }
                    )

    async def _send(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        text = json.dumps(payload, ensure_ascii=False)
        for client in tuple(self.clients):
            try:
                await client.send_text(text)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)
