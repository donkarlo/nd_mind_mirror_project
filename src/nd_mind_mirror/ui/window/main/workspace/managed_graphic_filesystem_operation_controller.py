"""Extend workspace moves so managed raster graphics keep their sidecars."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from nd_mind_mirror.graphic.core.sidecar_replacement_policy import (
    ManagedGraphicSidecarReplacementPolicy,
)
from nd_mind_mirror.ui.window.main.workspace.responsive_filesystem_operation_controller import (
    ResponsiveWorkspaceFilesystemOperationController,
)


class ManagedGraphicWorkspaceFilesystemOperationController(
    ResponsiveWorkspaceFilesystemOperationController
):
    """Move a raster image and its .ndgraphic sidecar as one managed document."""

    _IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}

    def request_moves(self, mappings: list[tuple[Path, Path]]) -> bool:
        """Add companion sidecar moves before delegating to the background worker."""
        normalized: list[tuple[Path, Path]] = []
        source_paths: set[Path] = set()
        destination_paths: set[Path] = set()

        for source, destination in mappings:
            source_path = Path(source).expanduser().resolve(strict=False)
            destination_path = Path(destination).expanduser().resolve(strict=False)
            if source_path == destination_path or source_path in source_paths:
                continue
            normalized.append((source_path, destination_path))
            source_paths.add(source_path)
            destination_paths.add(destination_path)

        companions: list[tuple[Path, Path]] = []
        for source_path, destination_path in normalized:
            if source_path.suffix.lower() not in self._IMAGE_SUFFIXES:
                continue
            sidecar = source_path.with_suffix(".ndgraphic")
            if not sidecar.is_file() or sidecar in source_paths:
                continue
            sidecar_destination = destination_path.with_suffix(".ndgraphic")
            if sidecar_destination in destination_paths:
                QMessageBox.warning(
                    self._panel,
                    "Move graphic",
                    f"{sidecar_destination.name} is already a destination in this move.",
                )
                return False
            if sidecar_destination.exists() or sidecar_destination.is_symlink():
                if not ManagedGraphicSidecarReplacementPolicy.can_replace(
                    sidecar,
                    sidecar_destination,
                ):
                    QMessageBox.warning(
                        self._panel,
                        "Move graphic",
                        f"{sidecar_destination.name} already exists in "
                        f"{sidecar_destination.parent}.",
                    )
                    return False
            companions.append((sidecar, sidecar_destination))
            source_paths.add(sidecar)
            destination_paths.add(sidecar_destination)

        return super().request_moves(normalized + companions)
