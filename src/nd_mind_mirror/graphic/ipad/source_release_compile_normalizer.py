"""Final compile/stability normalizer for the current iPad Swift package."""

from __future__ import annotations

from pathlib import Path


class IpadReleaseCompileNormalizer:
    """Repair known post-hotfix Swift composition mistakes idempotently."""

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        changed |= self._normalize_canvas_image_objects()
        changed |= self._normalize_pencil_canvas()
        return changed

    def _normalize_canvas_image_objects(self) -> bool:
        path = self.source_root / "Views" / "CanvasImageObjectViews.swift"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False

        updated = text.replace(
            "let fixed = point(for: opposite(corner), in: original)",
            "let fixed = self.point(for: opposite(corner), in: original)",
        )
        if updated == text:
            return False
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError:
            return False
        return True

    def _normalize_pencil_canvas(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return False

        updated = text.replace(
            "imageObjectInteractionView?.selectObject(inLasso: polygon)",
            "imageObjectInteractionView?.selectObject(inLasso: lassoPoints)",
        )

        duplicated = (
            "            if selected.isEmpty {\n"
            "                imageObjectInteractionView?.selectObject(inLasso: lassoPoints)\n"
            "            }\n"
            "            if selected.isEmpty {\n"
            "                imageObjectInteractionView?.selectObject(inLasso: lassoPoints)\n"
            "            }\n"
        )
        single = (
            "            if selected.isEmpty {\n"
            "                imageObjectInteractionView?.selectObject(inLasso: lassoPoints)\n"
            "            }\n"
        )
        while duplicated in updated:
            updated = updated.replace(duplicated, single)

        duplicate_frames = (
            "            coordinator.imageObjectLayer?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.imageObjectInteractionView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.imageObjectLayer?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.imageObjectInteractionView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
        )
        clean_frames = (
            "            coordinator.imageObjectLayer?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
            "            coordinator.imageObjectInteractionView?.frame = CGRect(origin: .zero, size: logicalCanvasSize)\n"
        )
        while duplicate_frames in updated:
            updated = updated.replace(duplicate_frames, clean_frames)

        if updated == text:
            return False
        try:
            path.write_text(updated, encoding="utf-8")
        except OSError:
            return False
        return True
