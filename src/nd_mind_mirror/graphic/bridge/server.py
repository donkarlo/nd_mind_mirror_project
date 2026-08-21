from __future__ import annotations

from pathlib import Path
import asyncio
import ipaddress
import subprocess
import socket
import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from watchfiles import awatch

from . import __version__


class GraphicBridgeServer:
    """Bridge Mind Mirror to the iPad graphic editor.

    Two transports are intentionally kept alive:

    * WebSocket on the Uvicorn port (default 8766) for browser/desktop clients.
    * Plain TCP JSON-lines on ``tcp_port`` (default 8767) for legacy clients.
    * Reverse TCP discovery for ND Graphic 0.30.6+: the iPad listens on 8768
      and Ubuntu connects to it. This avoids the Swift Playgrounds local-network
      privacy bug because the iPad no longer initiates a local TCP connection.
    """

    def __init__(
        self,
        workspace: str | Path,
        token: str = "",
        *,
        tcp_host: str = "0.0.0.0",
        tcp_port: int = 8767,
        ipad_listener_port: int = 8768,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.token = str(token)
        self.clients: set[WebSocket] = set()
        self.tcp_clients: set[asyncio.StreamWriter] = set()
        self.tcp_host = str(tcp_host)
        self.tcp_port = int(tcp_port)
        self.ipad_listener_port = int(ipad_listener_port)
        self._tcp_server: asyncio.AbstractServer | None = None
        self.max_tcp_message_bytes = 128 * 1024 * 1024
        self._reverse_scan_task: asyncio.Task[None] | None = None
        self._reverse_scan_round = 0
        self._hashes: dict[Path, str] = {}
        self._suppress_broadcast_until: dict[Path, float] = {}
        self.request_path = (
            self.workspace / ".nd_mind_mirror" / "graphic_open_request.json"
        )
        self.update_event_path = (
            self.workspace / ".nd_mind_mirror" / "graphic_update_event.json"
        )
        self.log_path = (
            Path("~/Desktop/repo/data/nd_mind_mirror_project/logs/graphic_bridge.log")
            .expanduser()
            .resolve()
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.current_sidecar: Path | None = None
        self.current_operation = "update"
        self.app = FastAPI(title="nd_mind_mirror_graphic_bridge", version=__version__)
        self.web_root = Path(__file__).resolve().parent.parent / "web"
        self.app.mount("/graphic", StaticFiles(directory=self.web_root, html=True), name="graphic")
        self.app.get("/")(self.http_root)
        self.app.get("/diagnostics/ping")(self.http_diagnostics_ping)
        self.app.websocket("/ws")(self.websocket_endpoint)
        self.app.post("/open-graphic")(self.http_open_graphic)
        self.app.on_event("startup")(self.startup)
        self.app.on_event("shutdown")(self.shutdown)

    async def http_root(self) -> RedirectResponse:
        return RedirectResponse(url="/graphic/")

    def _log_event(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        line = f"{stamp} {message}"
        print(f"[ND Graphic] {message}", flush=True)
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    async def http_diagnostics_ping(self, request: Request) -> dict[str, object]:
        client = request.client
        client_text = f"{client.host}:{client.port}" if client else "unknown"
        self._log_event(
            f"HTTP diagnostics ping from {client_text} "
            f"user-agent={request.headers.get('user-agent', '-')}"
        )
        return {
            "ok": True,
            "bridge_version": __version__,
            "client": client_text,
            "server_utc": datetime.now(timezone.utc).isoformat(),
            "websocket": "/ws",
        }

    async def startup(self) -> None:
        self._log_event(
            f"startup version={__version__} workspace={self.workspace} "
            f"websocket_port=8766 tcp={self.tcp_host}:{self.tcp_port} "
            f"ipad_listener_scan_port={self.ipad_listener_port} log={self.log_path}"
        )
        self._load_latest_request()
        self._tcp_server = await asyncio.start_server(
            self.tcp_client_connected,
            host=self.tcp_host,
            port=self.tcp_port,
            limit=self.max_tcp_message_bytes,
        )
        print(
            f"ND Graphic direct iPad bridge listening on "
            f"tcp://{self.tcp_host}:{self.tcp_port}",
            flush=True,
        )
        asyncio.create_task(self._watch_workspace())
        self._reverse_scan_task = asyncio.create_task(self._reverse_connector_loop())
        self._log_event(
            f"Ubuntu reverse connector will scan LAN for ND Graphic iPad listener "
            f"on tcp://<ipad>:{self.ipad_listener_port}"
        )

    async def shutdown(self) -> None:
        if self._reverse_scan_task is not None:
            self._reverse_scan_task.cancel()
            try:
                await self._reverse_scan_task
            except asyncio.CancelledError:
                pass
            self._reverse_scan_task = None
        if self._tcp_server is not None:
            self._tcp_server.close()
            await self._tcp_server.wait_closed()
            self._tcp_server = None
        for writer in tuple(self.tcp_clients):
            writer.close()
        self.tcp_clients.clear()

    async def _reverse_connector_loop(self) -> None:
        """Find an iPad that is *listening* and connect Ubuntu to it.

        This is intentionally the reverse of the older transport.  Apple local
        network privacy applies to outgoing connections from iPad apps, while
        listening for and accepting an incoming TCP connection does not require
        Local Network privilege.  Swift Playgrounds can therefore keep its
        networking sandbox out of the critical path.
        """
        while True:
            try:
                if not self.tcp_clients:
                    found = await self._discover_ipad_listener()
                    if found is not None:
                        host, reader, writer, greeting = found
                        await self._serve_reverse_ipad(host, reader, writer, greeting)
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_event(
                    f"Reverse iPad discovery error: {type(exc).__name__}: {exc}"
                )
                await asyncio.sleep(3.0)

    async def _discover_ipad_listener(
        self,
    ) -> tuple[str, asyncio.StreamReader, asyncio.StreamWriter, dict[str, Any]] | None:
        hosts = await self._candidate_lan_hosts()
        if not hosts:
            self._reverse_scan_round += 1
            if self._reverse_scan_round % 10 == 1:
                self._log_event("Reverse iPad discovery found no LAN IPv4 interface to scan")
            return None

        self._reverse_scan_round += 1
        if self._reverse_scan_round % 10 == 1:
            self._log_event(
                f"Reverse iPad discovery scanning {len(hosts)} LAN hosts "
                f"for tcp/{self.ipad_listener_port}"
            )

        semaphore = asyncio.Semaphore(64)

        async def probe(host: str):
            async with semaphore:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(
                            host,
                            self.ipad_listener_port,
                            limit=self.max_tcp_message_bytes,
                        ),
                        timeout=0.30,
                    )
                except (asyncio.TimeoutError, ConnectionError, OSError):
                    return None
                try:
                    greeting = await asyncio.wait_for(
                        self._read_tcp_json(reader), timeout=0.75
                    )
                    if str(greeting.get("type", "")) != "ipad_listener":
                        writer.close()
                        try:
                            await writer.wait_closed()
                        except Exception:
                            pass
                        return None
                    if self.token and str(greeting.get("token", "")) != self.token:
                        self._log_event(
                            f"Reverse iPad listener at {host} rejected: token mismatch"
                        )
                        writer.close()
                        try:
                            await writer.wait_closed()
                        except Exception:
                            pass
                        return None
                    return host, reader, writer, greeting
                except (asyncio.TimeoutError, OSError, ValueError, json.JSONDecodeError):
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    return None

        tasks = [asyncio.create_task(probe(host)) for host in hosts]
        try:
            for completed in asyncio.as_completed(tasks):
                result = await completed
                if result is not None:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return result
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        return None

    async def _candidate_lan_hosts(self) -> list[str]:
        """Return a bounded set of same-LAN IPv4 addresses to probe."""
        addresses: list[tuple[str, int]] = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "-j", "-4", "addr", "show", "up", "scope", "global",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            payload = json.loads(stdout.decode("utf-8") or "[]")
            for item in payload:
                ifname = str(item.get("ifname", ""))
                if ifname.startswith(("docker", "br-", "veth", "virbr", "lo")):
                    continue
                for info in item.get("addr_info", []):
                    if info.get("family") != "inet" or info.get("scope") != "global":
                        continue
                    local = str(info.get("local", ""))
                    prefix = int(info.get("prefixlen", 24))
                    if local:
                        addresses.append((local, prefix))
        except Exception:
            # Keep a small fallback for systems where iproute2 JSON output is
            # unavailable. gethostbyname_ex is imperfect but harmless here.
            try:
                for local in socket.gethostbyname_ex(socket.gethostname())[2]:
                    if not local.startswith("127."):
                        addresses.append((local, 24))
            except OSError:
                pass

        hosts: list[str] = []
        seen: set[str] = set()
        for local, prefix in addresses:
            try:
                interface = ipaddress.ip_interface(f"{local}/{prefix}")
            except ValueError:
                continue
            network = interface.network
            # Do not fan out across a huge corporate/VPN subnet.  For prefixes
            # wider than /24, scan the /24 containing the Ubuntu host first.
            if network.num_addresses > 512:
                network = ipaddress.ip_network(f"{local}/24", strict=False)
            for candidate in network.hosts():
                text = str(candidate)
                if text == local or text in seen:
                    continue
                seen.add(text)
                hosts.append(text)
        return hosts

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        greeting: dict[str, Any],
    ) -> None:
        version = str(greeting.get("version", "unknown"))
        self._log_event(
            f"Reverse iPad listener discovered at {host}:{self.ipad_listener_port} "
            f"version={version}"
        )
        self.tcp_clients.add(writer)
        try:
            await self._send_tcp(writer, {"type": "hello", "version": __version__})
            if self.current_sidecar is not None and self.current_sidecar.exists():
                await self._send_open_tcp(
                    writer,
                    self.current_sidecar,
                    "open_graphic",
                    operation=self.current_operation,
                )
            while True:
                payload = await self._read_tcp_json(reader)
                await self._handle_tcp(writer, payload)
        except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError) as exc:
            self._log_event(
                f"Reverse iPad connection closed {host}:{self.ipad_listener_port}: "
                f"{type(exc).__name__}"
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._log_event(
                f"Reverse iPad connection error {host}:{self.ipad_listener_port}: "
                f"{type(exc).__name__}: {exc}"
            )
        finally:
            self.tcp_clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

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

    # ------------------------------------------------------------------
    # Native iPad transport: plain TCP, one compact JSON object per line.
    # ------------------------------------------------------------------
    async def tcp_client_connected(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_text = f"{peer[0]}:{peer[1]}" if isinstance(peer, tuple) and len(peer) >= 2 else str(peer or "unknown")
        self._log_event(f"Direct TCP attempt from {peer_text}")
        registered = False
        try:
            if self.token:
                auth = await self._read_tcp_json(reader)
                if str(auth.get("type", "")) != "auth" or not self._authorized(
                    str(auth.get("token", ""))
                ):
                    await self._send_tcp(writer, {"type": "error", "message": "Invalid token"})
                    return

            self.tcp_clients.add(writer)
            registered = True
            self._log_event(f"Direct TCP accepted from {peer_text}")
            await self._send_tcp(writer, {"type": "hello", "version": __version__})
            if self.current_sidecar is not None and self.current_sidecar.exists():
                await self._send_open_tcp(
                    writer,
                    self.current_sidecar,
                    "open_graphic",
                    operation=self.current_operation,
                )

            while True:
                payload = await self._read_tcp_json(reader)
                await self._handle_tcp(writer, payload)
        except (asyncio.IncompleteReadError, ConnectionError, BrokenPipeError) as exc:
            self._log_event(f"Direct TCP disconnected from {peer_text}: {type(exc).__name__}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            self._log_event(f"Direct TCP error from {peer_text}: {type(exc).__name__}: {exc}")
            try:
                await self._send_tcp(writer, {"type": "error", "message": str(exc)})
            except Exception:
                pass
        finally:
            if registered:
                self.tcp_clients.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            if peer:
                self._log_event(f"Direct TCP closed from {peer_text}")

    @staticmethod
    async def _read_tcp_json(reader: asyncio.StreamReader) -> dict[str, Any]:
        raw = await reader.readline()
        if not raw:
            raise asyncio.IncompleteReadError(raw, None)
        if len(raw) > 128 * 1024 * 1024:
            raise ValueError("Graphic bridge message is too large")
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Graphic bridge message must be a JSON object")
        return value

    async def _handle_tcp(
        self,
        writer: asyncio.StreamWriter,
        payload: dict[str, Any],
    ) -> None:
        kind = str(payload.get("type", ""))
        try:
            if kind == "open_graphic":
                sidecar = self._resolve_sidecar(str(payload.get("path", "")))
                self.current_sidecar = sidecar
                self.current_operation = self._normalize_operation(payload.get("operation", "update"))
                await self._broadcast_open(
                    sidecar,
                    message_type="open_graphic",
                    operation=self.current_operation,
                )
                return
            if kind == "update_graphic":
                sidecar = self._resolve_sidecar(str(payload.get("path", "")))
                self.current_sidecar = sidecar
                _image_path, revision = await self._update_graphic(sidecar, payload)
                await self._send_tcp(
                    writer,
                    {
                        "type": "graphic_saved",
                        "path": sidecar.relative_to(self.workspace).as_posix(),
                        "client_revision": revision,
                    },
                )
                return
            if kind == "request_current":
                if self.current_sidecar is not None:
                    await self._send_open_tcp(
                        writer,
                        self.current_sidecar,
                        "open_graphic",
                        operation=self.current_operation,
                    )
                return
            await self._send_tcp(writer, {"type": "error", "message": f"Unknown message: {kind}"})
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            await self._send_tcp(writer, {"type": "error", "message": str(exc)})

    # ------------------------------------------------------------------
    # Existing WebSocket transport, retained for compatibility.
    # ------------------------------------------------------------------
    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        client = websocket.client
        client_text = f"{client.host}:{client.port}" if client else "unknown"
        self._log_event(
            f"WebSocket attempt from {client_text} "
            f"origin={websocket.headers.get('origin', '-')} "
            f"user-agent={websocket.headers.get('user-agent', '-')}"
        )
        if not self._authorized(websocket.query_params.get("token", "")):
            self._log_event(f"WebSocket rejected invalid token from {client_text}")
            await websocket.close(code=1008, reason="Invalid token")
            return
        await websocket.accept()
        self._log_event(f"WebSocket accepted from {client_text}")
        self.clients.add(websocket)
        await self._send(websocket, {"type": "hello", "version": __version__})
        if self.current_sidecar is not None and self.current_sidecar.exists():
            await self._send_open(websocket, self.current_sidecar, "open_graphic", operation=self.current_operation)
        try:
            while True:
                payload = await websocket.receive_json()
                await self._handle(websocket, payload)
        except WebSocketDisconnect as exc:
            self._log_event(f"WebSocket disconnected from {client_text} code={exc.code}")
        except Exception as exc:
            self._log_event(f"WebSocket error from {client_text}: {type(exc).__name__}: {exc}")
            raise
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
                _image_path, revision = await self._update_graphic(sidecar, payload)
                await self._send(
                    websocket,
                    {
                        "type": "graphic_saved",
                        "path": sidecar.relative_to(self.workspace).as_posix(),
                        "client_revision": revision,
                    },
                )
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

    async def _update_graphic(self, sidecar: Path, payload: dict[str, Any]) -> tuple[Path, int]:
        """Persist one iPad update and publish a tiny desktop-side event.

        The old implementation echoed the complete PNG and PencilKit payload
        back to the same iPad after every stroke. That needless multi-megabyte
        round trip made live drawing feel sluggish. The writer now gets a
        compact acknowledgement while the Ubuntu GUI notices the atomic event
        file immediately and refreshes Visual/Preview from the PNG on disk.
        """
        data, image_path = self._read_document(sidecar)
        for key in (
            "drawing_data_base64",
            "web_strokes",
            "canvas_width",
            "canvas_height",
            "pencil",
            "background_image_base64",
        ):
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

        revision = int(payload.get("client_revision", 0))
        suppress_until = time.monotonic() + 0.8
        self._suppress_broadcast_until[sidecar.resolve()] = suppress_until
        self._suppress_broadcast_until[image_path.resolve()] = suppress_until
        self._write_update_event(sidecar, image_path, revision)
        return image_path, revision

    def _write_update_event(
        self,
        sidecar: Path,
        image_path: Path,
        client_revision: int,
    ) -> None:
        """Atomically notify the Mind Mirror GUI that a graphic changed."""
        try:
            self.update_event_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "sidecar": sidecar.relative_to(self.workspace).as_posix(),
                "image": image_path.relative_to(self.workspace).as_posix(),
                "client_revision": int(client_revision),
                "time_ns": time.time_ns(),
            }
            temp = self.update_event_path.with_suffix(".tmp")
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temp.replace(self.update_event_path)
        except (OSError, ValueError):
            # Saving the PNG is the critical operation. A missed UI nudge can
            # still be recovered by the slower dependency polling path.
            return

    def _open_payload(
        self,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
        client_revision: int = 0,
    ) -> dict[str, Any]:
        data, image_path = self._read_document(sidecar)
        image_b64 = ""
        if image_path.exists():
            image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return {
            "type": message_type,
            "path": sidecar.relative_to(self.workspace).as_posix(),
            "operation": self._normalize_operation(operation or self.current_operation),
            "document": data,
            "png_base64": image_b64,
            "client_revision": int(client_revision),
        }

    async def _send_open(
        self, client: WebSocket, sidecar: Path, message_type: str, *, operation: str | None = None
    ) -> None:
        await self._send(
            client,
            self._open_payload(sidecar, message_type, operation=operation),
        )

    async def _send_open_tcp(
        self,
        writer: asyncio.StreamWriter,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
    ) -> None:
        await self._send_tcp(
            writer,
            self._open_payload(sidecar, message_type, operation=operation),
        )

    async def _broadcast_open(
        self,
        sidecar: Path,
        message_type: str,
        client_revision: int = 0,
        *,
        operation: str | None = None,
    ) -> None:
        payload_obj = self._open_payload(
            sidecar,
            message_type,
            operation=operation,
            client_revision=client_revision,
        )
        payload_text = json.dumps(payload_obj, ensure_ascii=False)

        dead_ws: list[WebSocket] = []
        for client in tuple(self.clients):
            try:
                await client.send_text(payload_text)
            except Exception:
                dead_ws.append(client)
        for client in dead_ws:
            self.clients.discard(client)

        dead_tcp: list[asyncio.StreamWriter] = []
        for writer in tuple(self.tcp_clients):
            try:
                await self._send_tcp(writer, payload_obj)
            except Exception:
                dead_tcp.append(writer)
        for writer in dead_tcp:
            self.tcp_clients.discard(writer)
            writer.close()

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
                _, image = self._read_document(self.current_sidecar)
            except Exception:
                continue
            watched = {self.current_sidecar.resolve(), image.resolve()}
            if not (graphic_changed & watched):
                continue
            changed_for_real = False
            now = time.monotonic()
            for path in graphic_changed & watched:
                if not path.exists():
                    continue
                if now < self._suppress_broadcast_until.get(path.resolve(), 0.0):
                    # This is the filesystem echo of a stroke just received
                    # from this iPad. A compact graphic_saved ACK was already
                    # sent; do not send the full document back and reset its
                    # live canvas/viewport.
                    self._hashes[path] = self._digest(path)
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

    @staticmethod
    async def _send_tcp(writer: asyncio.StreamWriter, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        writer.write(data + b"\n")
        await writer.drain()
