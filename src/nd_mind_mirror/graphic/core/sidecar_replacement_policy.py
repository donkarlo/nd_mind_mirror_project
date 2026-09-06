"""Decide when an existing managed graphic sidecar is a replaceable stale alias."""

from __future__ import annotations

import json
from pathlib import Path


class ManagedGraphicSidecarReplacementPolicy:
    """Recognize duplicate sidecars that point at the same managed image identity."""

    @classmethod
    def can_replace(cls, source_sidecar: Path, destination_sidecar: Path) -> bool:
        """Return True only when both sidecars describe the same current image."""
        source = cls._payload(source_sidecar)
        destination = cls._payload(destination_sidecar)
        if source is None or destination is None:
            return False

        source_image = str(source.get("image_name", "")).strip()
        destination_image = str(destination.get("image_name", "")).strip()
        if not source_image or source_image != destination_image:
            return False

        source_owner = str(source.get("source_name", "")).strip()
        destination_owner = str(destination.get("source_name", "")).strip()
        if source_owner and destination_owner and source_owner != destination_owner:
            return False
        return True

    @staticmethod
    def _payload(path: Path) -> dict[str, object] | None:
        """Read one sidecar payload without mutating it."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
