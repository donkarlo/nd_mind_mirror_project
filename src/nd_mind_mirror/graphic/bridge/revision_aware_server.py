"""Revision-aware bridge behavior that suppresses delayed filesystem echoes."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from .server_compat import PreservingGraphicBridgeServer


class RevisionAwareGraphicBridgeServer(PreservingGraphicBridgeServer):
    """Keep iPad-originated saves from returning as stale full-document updates."""

    _LOCAL_ECHO_SUPPRESSION_SECONDS = 6.0

    async def _update_graphic(
        self,
        sidecar: Path,
        payload: dict[str, Any],
    ) -> tuple[Path, int]:
        image_path, revision = await super()._update_graphic(sidecar, payload)
        suppress_until = time.monotonic() + self._LOCAL_ECHO_SUPPRESSION_SECONDS
        self._suppress_broadcast_until[sidecar.expanduser().resolve()] = suppress_until
        if image_path:
            self._suppress_broadcast_until[image_path.expanduser().resolve()] = suppress_until
        return image_path, revision
