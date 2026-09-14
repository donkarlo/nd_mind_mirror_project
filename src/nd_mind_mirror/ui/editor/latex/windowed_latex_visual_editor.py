"""Windowed Visual LaTeX editor with line deletion and asynchronous TikZ previews."""

from hashlib import sha256
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QImage,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
)

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_service import (
    TikZVisualPreviewService,
)
from nd_mind_mirror.ui.editor.latex.windowed_latex_visual_editor_core import (
    WindowedLatexVisualEditor as WindowedLatexVisualEditorCore,
)


class WindowedLatexVisualEditor(WindowedLatexVisualEditorCore):
    """Add direct TikZ input projection and Ctrl+Shift+D line deletion."""

    def __init__(self, settings_path, parent=None) -> None:
        super().__init__(settings_path, parent)
        workspace_root = getattr(
            getattr(parent, "_app_settings", None),
            "search_default_path",
            None,
        )
        self._tikz_visual_preview_service = (
            TikZVisualPreviewService(workspace_root, self)
            if workspace_root is not None
            else None
        )
        if self._tikz_visual_preview_service is not None:
            self._tikz_visual_preview_service.preview_ready.connect(
                self._on_tikz_preview_ready
            )

    def _insert_raw_block(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int = 0,
    ) -> None:
        service = self._tikz_visual_preview_service
        image = (
            service.preview_for_input(raw, self._source_path)
            if service is not None
            else None
        )
        if image is None or image.isNull():
            super()._insert_raw_block(cursor, raw, source_line=source_line)
            return
        self._insert_tikz_preview(cursor, raw, source_line, image)

    def _insert_tikz_preview(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int,
        image: QImage,
    ) -> None:
        digest = sha256(
            f"{self._source_path}:{source_line}:{raw}:{image.cacheKey()}".encode(
                "utf-8"
            )
        ).hexdigest()[:20]
        key = QUrl(f"ndtikz:{digest}")
        self.document().addResource(
            QTextDocument.ResourceType.ImageResource,
            key,
            image,
        )
        available = max(self.viewport().width() - 90, 260)
        width = min(float(image.width()), float(available))
        scale = width / max(float(image.width()), 1.0)
        image_format = QTextImageFormat()
        image_format.setName(key.toString())
        image_format.setWidth(width)
        image_format.setHeight(max(float(image.height()) * scale, 1.0))
        cursor.block().setUserData(
            _BlockMeta(
                kind="raw",
                raw=raw,
                display="TikZ preview",
                source_line=source_line,
            )
        )
        block_format = cursor.blockFormat()
        block_format.setTopMargin(8)
        block_format.setBottomMargin(8)
        cursor.setBlockFormat(block_format)
        cursor.insertImage(image_format)

    def _on_tikz_preview_ready(
        self,
        referring_file: str,
        raw: str,
        image: object,
    ) -> None:
        if not isinstance(image, QImage) or image.isNull():
            return
        if self._source_path is None:
            return
        try:
            if Path(referring_file).expanduser().resolve() != self._source_path:
                return
        except OSError:
            return

        matching_blocks: list[tuple[int, int]] = []
        block = self.document().firstBlock()
        while block.isValid():
            meta = block.userData()
            if (
                isinstance(meta, _BlockMeta)
                and meta.kind == "raw"
                and meta.raw == raw
            ):
                matching_blocks.append((block.position(), meta.source_line))
            block = block.next()

        if not matching_blocks:
            return

        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        document = self.document()
        was_modified = document.isModified()
        try:
            for position, source_line in reversed(matching_blocks):
                block = document.findBlock(position)
                if not block.isValid():
                    continue
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                self._insert_tikz_preview(
                    cursor,
                    raw,
                    source_line,
                    QImage(image),
                )
            document.setModified(was_modified)
        finally:
            self._loading = was_loading
        self.viewport().update()

    def keyPressEvent(self, event) -> None:
        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt_or_meta = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if (
            control
            and shift
            and not alt_or_meta
            and event.key() == Qt.Key.Key_D
        ):
            self._delete_current_visual_line()
            event.accept()
            return
        super().keyPressEvent(event)

    def _delete_current_visual_line(self) -> None:
        """Delete one Visual block while preserving following block metadata."""
        cursor = self.textCursor()
        block = cursor.block()
        if not block.isValid():
            return
        document = self.document()
        start = block.position()
        next_block = block.next()
        next_meta = None
        next_format = None
        if next_block.isValid():
            next_meta = self._copy_block_meta(next_block.userData())
            next_format = QTextBlockFormat(next_block.blockFormat())
        edit = QTextCursor(document)
        edit.beginEditBlock()
        if next_block.isValid():
            edit.setPosition(start)
            edit.setPosition(
                next_block.position(),
                QTextCursor.MoveMode.KeepAnchor,
            )
        else:
            previous = block.previous()
            if previous.isValid():
                edit.setPosition(max(start - 1, 0))
                edit.setPosition(
                    start + len(block.text()),
                    QTextCursor.MoveMode.KeepAnchor,
                )
            else:
                edit.select(QTextCursor.SelectionType.Document)
        edit.removeSelectedText()
        survivor = document.findBlock(start)
        if survivor.isValid():
            survivor.setUserData(next_meta)
            format_cursor = QTextCursor(survivor)
            format_cursor.setBlockFormat(
                next_format if next_format is not None else QTextBlockFormat()
            )
        edit.endEditBlock()
        restored = QTextCursor(document)
        restored.setPosition(
            min(max(start, 0), max(document.characterCount() - 1, 0))
        )
        self.setTextCursor(restored)
        self.ensureCursorVisible()

    @staticmethod
    def _copy_block_meta(data) -> _BlockMeta | None:
        if not isinstance(data, _BlockMeta):
            return None
        return _BlockMeta(
            kind=data.kind,
            command=data.command,
            raw=data.raw,
            display=data.display,
            depth=data.depth,
            source_line=data.source_line,
            source_segments=list(data.source_segments),
        )
