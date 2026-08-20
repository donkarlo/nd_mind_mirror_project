from __future__ import annotations

from pathlib import Path
import asyncio
import base64
import hashlib
import json
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from watchfiles import awatch

from . import __version__


class GraphicBridgeServer:
    def __init__(self, workspace: str | Path, token: str = "") -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.token = str(token)
        self.clients: set[WebSocket] = set()
        self._hashes: dict[Path, str] = {}
        self.request_path = (
            self.workspace / ".nd_mind_mirror" / "graphic_open_request.json"
        )
        self.current_sidecar: Path | None = None
        self.current_operation = "update"
        self.app = FastAPI(title="nd_mind_mirror_graphic_bridge", version=__version__)
        self.web_root = Path(__file__).resolve().parent.parent / "web"
        self.app.mount("/graphic", StaticFiles(directory=self.web_root, html=True), name="graphic")
        self.app.get("/")(self.http_root)
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.app.post("/open-graphic")(self.http_open_graphic)
        self.app.on_event("startup")(self.startup)

    async def http_root(self) -> RedirectResponse:
        return RedirectResponse(url="/graphic/")

    async def startup(self) -> None:
        self._load_latest_request()
        asyncio.create_task(self._watch_workspace())

    def _authorized(self, supplied: str) -> bool:
        return not self.token or supplied == self.token

    async def http_open_graphic(self, request: Request) -> dict[str, object]:
        if not self._authorized(request.query_params.get("token", "")):
            return {"ok": False, "error": "Invalid token"}
        payload = await request.json()
        path = self._resolve_sidecar(str(payload.get("path", "")))
        self.current_sidecar = path
        self.current_operation = self._normalize_operation(payload.get("operation", "update"))
        await self._broadcast_open(path, message_type="open_graphic", operation=self.current_operation)
        return {"ok": True}

    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        if not self._authorized(websocket.query_params.get("token", "")):
            await websocket.close(code=1008, reason="Invalid token")
            return
        await websocket.accept()
        self.clients.add(websocket)
        await self._send(websocket, {"type": "hello", "version": __version__})
        if self.current_sidecar is not None and self.current_sidecar.exists():
            await self._send_open(websocket, self.current_sidecar, "open_graphic", operation=self.current_operation)
        try:
            while True:
                payload = await websocket.receive_json()
                await self._handle(websocket, payload)
        except WebSocketDisconnect:
            pass
        finally:
            self.clients.discard(websocket)

    async def _handle(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        kind = str(payload.get("type", ""))
        try:
            if kind == "open_graphic":
                sidecar = self._resolve_sidecar(str(payload.get("path", "")))
                self.current_sidecar = sidecar
                self.current_operation = self._normalize_operation(payload.get("operation", "update"))
                await self._broadcast_open(sidecar, message_type="open_graphic", operation=self.current_operation)
                return
            if kind == "update_graphic":
                sidecar = self._resolve_sidecar(str(payload.get("path", "")))
                self.current_sidecar = sidecar
                await self._update_graphic(sidecar, payload)
                return
            if kind == "request_current":
                if self.current_sidecar is not None:
                    await self._send_open(websocket, self.current_sidecar, "open_graphic", operation=self.current_operation)
                return
            await self._send(websocket, {"type": "error", "message": f"Unknown message: {kind}"})
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            await self._send(websocket, {"type": "error", "message": str(exc)})

    def _resolve_sidecar(self, relative: str) -> Path:
        if not relative:
            raise ValueError("Graphic path is empty")
        path = (self.workspace / relative).resolve()
        try:
            path.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("Graphic path must stay inside the workspace") from exc
        if path.suffix.lower() != ".ndgraphic":
            raise ValueError("Graphic document must use .ndgraphic")
        if not path.exists():
            raise ValueError(f"Graphic document does not exist: {relative}")
        return path

    def _read_document(self, sidecar: Path) -> tuple[dict[str, Any], Path]:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        image_name = str(data.get("image_name", sidecar.with_suffix(".png").name))
        image_path = (sidecar.parent / image_name).resolve()
        try:
            image_path.relative_to(self.workspace)
        except ValueError as exc:
            raise ValueError("Graphic image must stay inside the workspace") from exc
        return data, image_path

    async def _update_graphic(self, sidecar: Path, payload: dict[str, Any]) -> None:
        data, image_path = self._read_document(sidecar)
        for key in ("drawing_data_base64", "web_strokes", "canvas_width", "canvas_height", "pencil"):
            if key in payload:
                data[key] = payload[key]
        png_base64 = str(payload.get("png_base64", ""))
        if png_base64:
            png = base64.b64decode(png_base64, validate=True)
            temp_image = image_path.with_suffix(image_path.suffix + ".tmp")
            temp_image.write_bytes(png)
            temp_image.replace(image_path)
            self._hashes[image_path] = self._digest(image_path)

        temp = sidecar.with_suffix(sidecar.suffix + ".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(sidecar)
        self._hashes[sidecar] = self._digest(sidecar)
        await self._broadcast_open(
            sidecar,
            message_type="graphic_updated",
            client_revision=int(payload.get("client_revision", 0)),
        )

    async def _send_open(
        self, client: WebSocket, sidecar: Path, message_type: str, *, operation: str | None = None
    ) -> None:
        data, image_path = self._read_document(sidecar)
        image_b64 = ""
        if image_path.exists():
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        await self._send(
            client,
            {
                "type": message_type,
                "path": sidecar.relative_to(self.workspace).as_posix(),
                "operation": self._normalize_operation(operation or self.current_operation),
                "document": data,
                "png_base64": image_b64,
                "client_revision": 0,
            },
        )

    async def _broadcast_open(
        self,
        sidecar: Path,
        message_type: str,
        client_revision: int = 0,
        *,
        operation: str | None = None,
    ) -> None:
        dead: list[WebSocket] = []
        data, image_path = self._read_document(sidecar)
        image_b64 = ""
        if image_path.exists():
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload = json.dumps(
            {
                "type": message_type,
                "path": sidecar.relative_to(self.workspace).as_posix(),
                "operation": self._normalize_operation(operation or self.current_operation),
                "document": data,
                "png_base64": image_b64,
                "client_revision": int(client_revision),
            },
            ensure_ascii=False,
        )
        for client in tuple(self.clients):
            try:
                await client.send_text(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.clients.discard(client)

    async def _watch_workspace(self) -> None:
        async for changes in awatch(self.workspace, debounce=150):
            request_changed = False
            graphic_changed: set[Path] = set()
            for _, raw in changes:
                path = Path(raw).resolve()
                if path == self.request_path.resolve():
                    request_changed = True
                    continue
                if path.suffix.lower() in {".ndgraphic", ".png"}:
                    graphic_changed.add(path)
            if request_changed:
                previous = self.current_sidecar
                self._load_latest_request()
                if self.current_sidecar is not None and self.current_sidecar != previous:
                    try:
                        await self._broadcast_open(
                            self.current_sidecar, "open_graphic", operation=self.current_operation
                        )
                    except Exception:
                        pass
            if self.current_sidecar is None:
                continue
            try:
                data, image = self._read_document(self.current_sidecar)
            except Exception:
                continue
            watched = {self.current_sidecar.resolve(), image.resolve()}
            if not (graphic_changed & watched):
                continue
            changed_for_real = False
            for path in graphic_changed & watched:
                if not path.exists():
                    continue
                digest = self._digest(path)
                if self._hashes.get(path) != digest:
                    self._hashes[path] = digest
                    changed_for_real = True
            if changed_for_real:
                try:
                    await self._broadcast_open(self.current_sidecar, "graphic_updated")
                except Exception:
                    pass

    def _load_latest_request(self) -> None:
        try:
            payload = json.loads(self.request_path.read_text(encoding="utf-8"))
            self.current_sidecar = self._resolve_sidecar(str(payload.get("path", "")))
            self.current_operation = self._normalize_operation(payload.get("operation", "update"))
        except Exception:
            return

    @staticmethod
    def _normalize_operation(value: object) -> str:
        return "insert" if str(value).lower() == "insert" else "update"

    @staticmethod
    def _digest(path: Path) -> str:
        return hashlib.sha1(path.read_bytes()).hexdigest()

    @staticmethod
    async def _send(client: WebSocket, payload: dict[str, Any]) -> None:
        await client.send_text(json.dumps(payload, ensure_ascii=False))
