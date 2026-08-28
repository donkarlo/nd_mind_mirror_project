"""Bridge compatibility helpers for editable PNG/JPEG backgrounds and recent iPad documents."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import time
from typing import Any

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from . import __version__
from .server import GraphicBridgeServer


class PreservingGraphicBridgeServer(GraphicBridgeServer):
    """Preserve PNG backgrounds, image objects, and resilient iPad transports."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._inferred_background_sidecars: set[Path] = set()

    async def startup(self) -> None:
        """Start primary transports; a busy legacy TCP port must not abort the bridge."""
        self._log_event(
            f"startup version={__version__} workspace={self.workspace} "
            f"websocket_port=8766 tcp={self.tcp_host}:{self.tcp_port} "
            f"ipad_listener_scan_port={self.ipad_listener_port} log={self.log_path}"
        )

        self.current_sidecar = None
        self.current_operation = "update"

        try:
            self._tcp_server = await asyncio.start_server(
                self.tcp_client_connected,
                host=self.tcp_host,
                port=self.tcp_port,
                limit=self.max_tcp_message_bytes,
            )
            print(
                f"ND Graphic legacy direct TCP listening on "
                f"tcp://{self.tcp_host}:{self.tcp_port}",
                flush=True,
            )
        except OSError as exc:
            self._tcp_server = None
            if getattr(exc, "errno", None) in {48, 98, 10048}:
                self._log_event(
                    f"Legacy direct TCP {self.tcp_host}:{self.tcp_port} is already in use; "
                    "continuing with WebSocket and reverse iPad transport"
                )
            else:
                raise

        asyncio.create_task(self._watch_workspace())
        self._reverse_scan_task = asyncio.create_task(self._reverse_connector_loop())
        self._log_event(
            f"Ubuntu reverse connector will scan LAN for ND Graphic iPad listener "
            f"on tcp://<ipad>:{self.ipad_listener_port}"
        )

    def _open_payload(
        self,
        sidecar: Path,
        message_type: str,
        *,
        operation: str | None = None,
        client_revision: int = 0,
    ) -> dict[str, Any]:
        payload = super()._open_payload(
            sidecar,
            message_type,
            operation=operation,
            client_revision=client_revision,
        )
        document = payload.get("document")
        png_base64 = str(payload.get("png_base64", "") or "")
        if not isinstance(document, dict):
            return payload

        try:
            sidecar_data, _image_path = self._read_document(sidecar)
        except (OSError, ValueError):
            sidecar_data = {}
        image_objects = sidecar_data.get("image_objects")
        if isinstance(image_objects, list):
            merged = dict(document)
            merged["image_objects"] = image_objects
            payload["document"] = merged
            document = merged

        if not png_base64:
            return payload

        drawing = str(document.get("drawing_data_base64", "") or "")
        background = str(document.get("background_image_base64", "") or "")
        if drawing or background or image_objects:
            return payload

        merged = dict(document)
        merged["background_image_base64"] = png_base64
        payload["document"] = merged
        self._inferred_background_sidecars.add(sidecar.expanduser().resolve())
        return payload

    async def _update_graphic(
        self,
        sidecar: Path,
        payload: dict[str, Any],
    ) -> tuple[Path, int]:
        resolved = sidecar.expanduser().resolve()
        update = dict(payload)
        injected = False

        # ND_MIGRATION4_JPEG_PRESERVE
        # The iPad renderer sends a lossless PNG composite. If the LaTeX image
        # being edited is .jpg/.jpeg, encode that composite back to JPEG before
        # the base bridge atomically replaces the target file.
        try:
            _sidecar_data, target_image_path = self._read_document(sidecar)
        except (OSError, ValueError):
            target_image_path = Path()
        if target_image_path.suffix.lower() in {".jpg", ".jpeg"}:
            encoded = str(update.get("png_base64", "") or "")
            if encoded:
                try:
                    raw = base64.b64decode(encoded, validate=True)
                    image = QImage.fromData(raw)
                    if not image.isNull():
                        buffer = QBuffer()
                        if buffer.open(QIODevice.OpenModeFlag.WriteOnly):
                            if image.save(buffer, "JPG", 95):
                                update["png_base64"] = base64.b64encode(
                                    bytes(buffer.data())
                                ).decode("ascii")
                            buffer.close()
                except Exception:
                    pass

        if resolved in self._inferred_background_sidecars and "background_image_base64" not in update:
            try:
                _data, image_path = self._read_document(sidecar)
                if image_path.is_file():
                    update["background_image_base64"] = base64.b64encode(
                        image_path.read_bytes()
                    ).decode("ascii")
                    injected = True
            except (OSError, ValueError):
                pass

        result = await super()._update_graphic(sidecar, update)

        if "image_objects" in update:
            try:
                data, _image_path = self._read_document(sidecar)
                raw_objects = update.get("image_objects")
                data["image_objects"] = raw_objects if isinstance(raw_objects, list) else []
                temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
                temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
                temporary.replace(sidecar)
                self._hashes[sidecar] = self._digest(sidecar)
                self._suppress_broadcast_until[sidecar.resolve()] = time.monotonic() + 0.8
            except (OSError, ValueError, TypeError):
                pass

        if injected:
            self._inferred_background_sidecars.discard(resolved)
        return result

    async def _handle_tcp(
        self,
        writer,
        payload: dict[str, Any],
    ) -> None:
        """Handle the iPad recent-document request before normal bridge messages."""
        if str(payload.get("type", "")) == "open_recent_graphic":
            try:
                sidecar = self._resolve_sidecar(str(payload.get("path", "")))
            except (OSError, ValueError):
                await self._send_tcp(
                    writer,
                    {"type": "error", "message": "Recent graphic is no longer available"},
                )
                return
            self.current_sidecar = sidecar
            self.current_operation = "update"
            await self._send_open_tcp(
                writer,
                sidecar,
                "open_graphic",
                operation="update",
            )
            return

        await super()._handle_tcp(writer, payload)
