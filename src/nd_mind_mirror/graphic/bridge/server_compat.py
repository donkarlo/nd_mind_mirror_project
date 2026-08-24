"""Compatibility bridge that treats ordinary PNGs as editable iPad backgrounds without losing them."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .server import GraphicBridgeServer


class PreservingGraphicBridgeServer(GraphicBridgeServer):
    """Preserve a pre-existing PNG when a newly-created sidecar has no editable background yet."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._inferred_background_sidecars: set[Path] = set()

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
        if not isinstance(document, dict) or not png_base64:
            return payload

        drawing = str(document.get("drawing_data_base64", "") or "")
        background = str(document.get("background_image_base64", "") or "")
        if drawing or background:
            return payload

        # A sidecar created on demand for an ordinary existing PNG starts with
        # no PencilKit/background payload. Send that real PNG as the initial
        # background instead of displaying an empty white canvas on the iPad.
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

        if (
            resolved in self._inferred_background_sidecars
            and "background_image_base64" not in update
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
        if injected:
            self._inferred_background_sidecars.discard(resolved)
        return result
