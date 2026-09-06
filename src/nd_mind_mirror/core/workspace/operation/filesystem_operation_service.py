"""Execute workspace filesystem move and delete batches outside the Qt process."""

from __future__ import annotations

from pathlib import Path
import shutil

from nd_mind_mirror.graphic.core.sidecar_replacement_policy import (
    ManagedGraphicSidecarReplacementPolicy,
)


class WorkspaceFilesystemOperationService:
    """Apply validated move/delete requests and report each result independently."""

    def execute(self, request: dict[str, object]) -> dict[str, object]:
        """Execute one serialized operation batch without raising per-entry failures."""
        return {
            "moves": self._execute_moves(request.get("moves")),
            "deletes": self._execute_deletes(request.get("deletes")),
        }

    def _execute_moves(self, raw_moves: object) -> list[dict[str, object]]:
        """Move each requested source to its exact destination in request order."""
        results: list[dict[str, object]] = []
        if not isinstance(raw_moves, list):
            return results

        # Capture replaceability before the first move mutates sibling paths.
        # This matters for an orphan destination sidecar: the raster move may
        # create its new sibling before the sidecar move executes.
        replaceable_destinations = self._replaceable_move_destinations(raw_moves)

        for item in raw_moves:
            if not isinstance(item, dict):
                continue
            source_text = str(item.get("source", ""))
            destination_text = str(item.get("destination", ""))
            result = {
                "source": source_text,
                "destination": destination_text,
                "success": False,
                "error": "",
            }
            try:
                source = Path(source_text).expanduser().resolve(strict=False)
                destination = Path(destination_text).expanduser().resolve(strict=False)
                if not source.exists() and not source.is_symlink():
                    raise FileNotFoundError(f"Source does not exist: {source}")
                destination.parent.mkdir(parents=True, exist_ok=True)

                if destination.exists() or destination.is_symlink():
                    if destination not in replaceable_destinations:
                        raise FileExistsError(
                            f"Destination already exists: {destination}"
                        )
                    source.replace(destination)
                    moved = destination
                else:
                    moved = Path(
                        shutil.move(str(source), str(destination))
                    ).resolve(strict=False)

                if moved != destination and not destination.exists():
                    raise OSError(f"Move did not create destination: {destination}")
                result["success"] = True
            except Exception as exc:
                result["error"] = str(exc)
            results.append(result)
        return results

    @classmethod
    def _replaceable_move_destinations(cls, raw_moves: list[object]) -> set[Path]:
        """Evaluate managed-sidecar replacement against the untouched batch state."""
        replaceable: set[Path] = set()
        for item in raw_moves:
            if not isinstance(item, dict):
                continue
            source = Path(str(item.get("source", ""))).expanduser().resolve(strict=False)
            destination = Path(str(item.get("destination", ""))).expanduser().resolve(strict=False)
            if not destination.exists() and not destination.is_symlink():
                continue
            if cls._can_replace_destination(source, destination):
                replaceable.add(destination)
        return replaceable

    @staticmethod
    def _can_replace_destination(source: Path, destination: Path) -> bool:
        """Allow only a safe managed-sidecar destination to be atomically replaced."""
        if (
            source.suffix.lower() != ".ndgraphic"
            or destination.suffix.lower() != ".ndgraphic"
            or not source.is_file()
            or not destination.is_file()
        ):
            return False
        return ManagedGraphicSidecarReplacementPolicy.can_replace(
            source,
            destination,
        )

    def _execute_deletes(self, raw_deletes: object) -> list[dict[str, object]]:
        """Delete each requested file/folder while reporting failures independently."""
        results: list[dict[str, object]] = []
        if not isinstance(raw_deletes, list):
            return results
        for raw_path in raw_deletes:
            path_text = str(raw_path)
            result = {"path": path_text, "success": False, "error": ""}
            try:
                path = Path(path_text).expanduser().resolve(strict=False)
                if path.is_symlink() or path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
                else:
                    raise FileNotFoundError(f"Path does not exist: {path}")
                result["success"] = True
            except Exception as exc:
                result["error"] = str(exc)
            results.append(result)
        return results
