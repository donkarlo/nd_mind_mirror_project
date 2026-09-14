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
from .document import GraphicDocumentBackgroundResolver
from .server import GraphicBridgeServer


class PreservingGraphicBridgeServer(GraphicBridgeServer):
    """Preserve image backgrounds and reject destructive blank iPad renders."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._inferred_background_sidecars: set[Path] = set()
        self._background_resolver = GraphicDocumentBackgroundResolver()

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
        if not isinstance(document, dict):
            return payload

        try:
            sidecar_data, _image_path = self._read_document(sidecar)
        except (OSError, ValueError):
            sidecar_data = {}

        image_objects = sidecar_data.get("image_objects")
        if isinstance(image_objects, list):
            document = dict(document)
            document["image_objects"] = image_objects

        paired_image_base64 = str(payload.get("png_base64", "") or "")
        resolved_document, recovered = self._background_resolver.resolve_for_open(
            document,
            paired_image_base64,
        )
        payload["document"] = resolved_document

        if recovered:
            resolved_sidecar = sidecar.expanduser().resolve()
            self._inferred_background_sidecars.add(resolved_sidecar)
            self._log_event(
                f"Recovered graphic background from authoritative paired image: {sidecar}"
            )

        return payload

    @staticmethod
    def _drop_empty_background_mutation(update: dict[str, Any]) -> None:
        """Do not let an accidental empty render erase the stored source background."""
        if "background_image_base64" in update and not str(
            update.get("background_image_base64", "") or ""
        ):
            update.pop("background_image_base64", None)

    @staticmethod
    def _replaces_editable_layers(update: dict[str, Any]) -> bool:
        """Return whether an update replaces every editable layer flattened into recovery."""

        return (
            "drawing_data_base64" in update
            and "image_objects" in update
        )

    def _clear_active_graphic_if_idle(self, transport: str) -> None:
        """Forget the previous document after the last client disconnects."""
        if self.tcp_clients or self.clients:
            return
        if self.current_sidecar is not None:
            self._log_event(
                f"Cleared active graphic after {transport} disconnect: {self.current_sidecar}"
            )
        self.current_sidecar = None
        self.current_operation = "update"

    async def _serve_reverse_ipad(
        self,
        host: str,
        reader,
        writer,
        greeting: dict[str, Any],
    ) -> None:
        try:
            await super()._serve_reverse_ipad(host, reader, writer, greeting)
        finally:
            self._clear_active_graphic_if_idle("reverse iPad")

    async def tcp_client_connected(self, reader, writer) -> None:
        try:
            await super().tcp_client_connected(reader, writer)
        finally:
            self._clear_active_graphic_if_idle("direct TCP")

    async def websocket_endpoint(self, websocket) -> None:
        try:
            await super().websocket_endpoint(websocket)
        finally:
            self._clear_active_graphic_if_idle("WebSocket")

    def _protect_existing_image_from_blank_render(
        self,
        update: dict[str, Any],
        target_image_path: Path,
    ) -> None:
        """Drop only a suspicious PNG replacement while allowing sidecar metadata to save."""
        encoded = str(update.get("png_base64", "") or "")
        if not encoded or not target_image_path.is_file():
            return

        candidate = self._background_resolver.decode_base64_image(encoded)
        if candidate is None:
            update["png_base64"] = ""
            self._drop_empty_background_mutation(update)
            self._log_event(
                f"Blocked invalid iPad image replacement for {target_image_path}"
            )
            return

        existing = QImage(str(target_image_path))
        if existing.isNull():
            return

        if self._background_resolver.is_suspicious_blank_replacement(
            candidate,
            existing,
        ):
            update["png_base64"] = ""
            self._drop_empty_background_mutation(update)
            candidate_fraction = self._background_resolver.informative_pixel_fraction(
                candidate
            )
            existing_fraction = self._background_resolver.informative_pixel_fraction(
                existing
            )
            self._log_event(
                "Blocked near-white iPad render; preserved existing image "
                f"path={target_image_path} existing_info={existing_fraction:.4f} "
                f"candidate_info={candidate_fraction:.4f}"
            )

    async def _update_graphic(
        self,
        sidecar: Path,
        payload: dict[str, Any],
    ) -> tuple[Path, int]:
        resolved = sidecar.expanduser().resolve()
        update = dict(payload)
        injected = False

        try:
            _sidecar_data, target_image_path = self._read_document(sidecar)
        except (OSError, ValueError):
            target_image_path = Path()

        self._protect_existing_image_from_blank_render(update, target_image_path)

        # The iPad renderer sends a lossless PNG composite. JPEG targets are
        # encoded back to JPEG before the base bridge atomically replaces them.
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

        # A recovered paired image already contains the legacy editable layers.
        # Persist it as the new background only when the same save also replaces
        # every editable layer that was flattened into that image.  Metadata-only
        # updates such as canvas resize must never combine the recovered composite
        # with stale on-disk PencilKit/image-object data, which would duplicate it.
        if (
            resolved in self._inferred_background_sidecars
            and "background_image_base64" not in update
            and self._replaces_editable_layers(update)
        ):
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
                data["image_objects"] = (
                    raw_objects if isinstance(raw_objects, list) else []
                )
                temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
                temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
                temporary.replace(sidecar)
                self._hashes[sidecar] = self._digest(sidecar)
                self._suppress_broadcast_until[sidecar.resolve()] = (
                    time.monotonic() + 0.8
                )
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
