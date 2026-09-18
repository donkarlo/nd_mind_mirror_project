"""Targeted Source-mode TikZ preview refreshes for external iPad edits."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage
from shiboken6 import isValid

from nd_mind_mirror.ui.editor.latex.source_tikz_preview_controller import (
    SourceTikZPreviewController,
)


class SourceTikZTargetedPreviewController(SourceTikZPreviewController):
    """Replace only the Source preview whose referenced TikZ file changed."""

    def notify_tikz_changed(self, path: str | Path) -> None:
        target = Path(path).expanduser().resolve(strict=False)
        editor = self._current_live_editor()
        if editor is not self._active_editor:
            # A tab/view transition legitimately needs the normal one-time rebuild.
            self.schedule_refresh()
            return
        self._refresh_target(editor, target)

    def _refresh_target(self, editor, target: Path) -> bool:
        if editor is None or editor.edit_mode != "source":
            return False

        viewport = self._viewport(editor)
        document = editor.document()
        if viewport is None or not isValid(document):
            return False

        source = editor.toPlainText()
        available = max(viewport.width() - 32, 120)
        changed = False

        for match in self._INPUT.finditer(source):
            raw = match.group(0)
            resolved = self._service.target_for_input(raw, editor.source_path)
            if resolved is None or resolved != target:
                continue

            image = self._service.preview_for_input(raw, editor.source_path)
            if image is None or image.isNull():
                continue

            block = document.findBlock(match.start())
            if not block.isValid():
                continue

            native_width = max(int(image.width()), 1)
            width = min(
                native_width,
                max(int(available * self._MAX_WIDTH_RATIO), 1),
            )
            scale = width / native_width
            height = max(int(round(float(image.height()) * scale)) + 6, 1)
            block_position = block.position()
            replacement = {
                "block_position": block_position,
                "image": QImage(image),
                "width": width,
                "height": height,
            }

            replaced = False
            for index, item in enumerate(self._layout):
                if int(item["block_position"]) == block_position:
                    self._layout[index] = replacement
                    replaced = True
                    break
            if not replaced:
                self._layout.append(replacement)

            self._apply_reserved_space(
                editor,
                {
                    block_position: height + (self._IMAGE_GAP_PX * 2),
                },
            )
            changed = True

        if changed:
            self._layout.sort(key=lambda item: int(item["block_position"]))
            self._layout_viewport_width = viewport.width()
            self.refresh_positions()
        return changed

    def _on_preview_ready(
        self,
        referring_file: str,
        raw: str,
        image: object,
    ) -> None:
        if not isinstance(image, QImage) or image.isNull():
            return
        editor = self._current_live_editor()
        if editor is None or editor is not self._active_editor:
            return
        try:
            if Path(referring_file).expanduser().resolve() != editor.source_path:
                return
        except (OSError, RuntimeError):
            return
        target = self._service.target_for_input(raw, editor.source_path)
        if target is not None:
            self._refresh_target(editor, target)
