"""Decide when an existing managed graphic sidecar may be safely replaced."""

from __future__ import annotations

import json
from pathlib import Path


class ManagedGraphicSidecarReplacementPolicy:
    """Recognize duplicate or orphan sidecars that are safe managed-graphic destinations."""

    _IMAGE_SUFFIXES = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
    }

    @classmethod
    def can_replace(cls, source_sidecar: Path, destination_sidecar: Path) -> bool:
        """Allow the same identity, or a stale orphan destination owned by the same source."""
        source_path = Path(source_sidecar).expanduser().resolve(strict=False)
        destination_path = Path(destination_sidecar).expanduser().resolve(strict=False)
        source = cls._payload(source_path)
        destination = cls._payload(destination_path)
        if source is None or destination is None:
            return False

        source_owner = str(source.get("source_name", "")).strip()
        destination_owner = str(destination.get("source_name", "")).strip()
        if source_owner and destination_owner and source_owner != destination_owner:
            return False

        source_image = str(source.get("image_name", "")).strip()
        destination_image = str(destination.get("image_name", "")).strip()
        if not source_image or not destination_image:
            return False

        if source_image == destination_image:
            return True

        destination_image_path = cls._managed_image_path(
            destination_path,
            destination_image,
        )
        if destination_image_path is None or destination_image_path.exists():
            return False
        return destination_image_path.stem == destination_path.stem

    @classmethod
    def _managed_image_path(
        cls,
        sidecar_path: Path,
        image_name: str,
    ) -> Path | None:
        """Return the sidecar-local raster named by its payload when it is well formed."""
        image = Path(str(image_name).strip())
        if image.name != str(image_name).strip():
            return None
        if image.suffix.lower() not in cls._IMAGE_SUFFIXES:
            return None
        return sidecar_path.with_name(image.name).resolve(strict=False)

    @staticmethod
    def _payload(path: Path) -> dict[str, object] | None:
        """Read one sidecar payload without mutating it."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
