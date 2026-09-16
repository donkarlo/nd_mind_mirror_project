"""Windowed Visual LaTeX editor with live graphics, math, and editable tables."""

from hashlib import sha256
from pathlib import Path
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QContextMenuEvent,
    QImage,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
)

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import (
    _BlockMeta,
    _RAW_LATEX_PROPERTY,
)
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_service import (
    TikZVisualPreviewService,
)
from nd_mind_mirror.ui.editor.latex.visual.latex_visual_document_serializer import (
    LatexVisualDocumentSerializer,
)
from nd_mind_mirror.ui.editor.latex.visual.math.latex_math_visual_preview_service import (
    LatexMathVisualPreviewService,
)
from nd_mind_mirror.ui.editor.latex.visual.table.latex_table_visual_controller import (
    LatexTableVisualController,
)
from nd_mind_mirror.ui.editor.latex.windowed_latex_visual_editor_core import (
    WindowedLatexVisualEditor as WindowedLatexVisualEditorCore,
)


class WindowedLatexVisualEditor(WindowedLatexVisualEditorCore):
    """Project source-backed TikZ, math, and tabular content into Visual mode."""

    _TIKZ_INPUT = re.compile(
        r"^\s*\\(?:input|include)\s*\{[^}]+\}\s*(?:%.*)?$"
    )

    @classmethod
    def _parse_body(
        cls,
        body: str,
        base_line: int = 1,
    ) -> list[tuple]:
        """Keep multi-line \\[ ... \\] display math as one canonical raw block."""
        parsed = list(super()._parse_body(body, base_line))
        source_lines = body.splitlines()
        merged: list[tuple] = []
        index = 0
        while index < len(parsed):
            block = parsed[index]
            if (
                block[0] == "raw"
                and len(block) >= 3
                and str(block[1]).strip() == r"\["
            ):
                start_line = int(block[2])
                end_index = index + 1
                while end_index < len(parsed):
                    candidate = parsed[end_index]
                    if (
                        candidate[0] == "raw"
                        and len(candidate) >= 3
                        and str(candidate[1]).strip() == r"\]"
                    ):
                        end_line = int(candidate[2])
                        first = max(start_line - int(base_line), 0)
                        last = max(end_line - int(base_line), first)
                        raw = "\n".join(source_lines[first : last + 1])
                        merged.append(("raw", raw, start_line))
                        index = end_index + 1
                        break
                    end_index += 1
                else:
                    merged.append(block)
                    index += 1
                continue
            merged.append(block)
            index += 1
        return merged

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

        self._math_visual_preview_service = LatexMathVisualPreviewService(self)
        self._math_visual_preview_service.preview_ready.connect(
            self._on_math_preview_ready
        )
        self._table_visual_controller = LatexTableVisualController(self)
        self._visual_document_serializer = LatexVisualDocumentSerializer(
            self,
            self._table_visual_controller,
        )

    def _insert_raw_block(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int = 0,
    ) -> None:
        if self._table_visual_controller.insert_if_supported(
            cursor,
            raw,
            source_line,
        ):
            return

        if self._math_visual_preview_service.is_display_math(raw):
            image = self._math_visual_preview_service.request(raw)
            if image is not None and not image.isNull():
                self._insert_math_preview(cursor, raw, source_line, image)
            else:
                super()._insert_raw_block(cursor, raw, source_line=source_line)
            return

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

    def _insert_inline_latex(self, cursor: QTextCursor, text: str) -> None:
        """Keep the base inline parser, then upgrade math tokens to cached images."""
        super()._insert_inline_latex(cursor, text)
        self._request_inline_math_for_block(cursor.block())

    def serialized_source(self) -> str:
        """Use the existing serializer unless native Visual tables are present."""
        if not self._table_visual_controller.has_tables():
            return super().serialized_source()
        serialized_window = self._visual_document_serializer.serialize()
        return self._source_window.splice(serialized_window)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        click_cursor = self.cursorForPosition(event.pos())
        table = self._table_visual_controller.table_at_cursor(click_cursor)
        if table is None:
            super().contextMenuEvent(event)
            return

        self.setTextCursor(click_cursor)
        menu = self.createStandardContextMenu()
        actions = self._table_visual_controller.build_context_actions(
            menu,
            click_cursor,
        )
        chosen = menu.exec(event.globalPos())
        if self._table_visual_controller.apply_context_action(
            chosen,
            actions,
            click_cursor,
        ):
            self.document().setModified(True)
            self._schedule_source_emit()
            self.viewport().update()

    def refresh_graphic_resources(self) -> bool:
        """Refresh normal graphics and TikZ images without rebuilding Visual mode."""
        refreshed_graphics = super().refresh_graphic_resources()
        refreshed_tikz = self.refresh_tikz_resources()
        return bool(refreshed_graphics or refreshed_tikz)

    def refresh_tikz_resources(self) -> bool:
        """Request current TikZ generations for visible raw input/include blocks."""
        service = self._tikz_visual_preview_service
        if service is None or self._source_path is None:
            return False

        requests: list[tuple[int, str, int]] = []
        block = self.document().firstBlock()
        while block.isValid():
            meta = block.userData()
            if (
                isinstance(meta, _BlockMeta)
                and meta.kind == "raw"
                and self._TIKZ_INPUT.match(meta.raw.strip()) is not None
            ):
                requests.append(
                    (
                        block.position(),
                        meta.raw,
                        meta.source_line,
                    )
                )
            block = block.next()

        for position, raw, source_line in requests:
            image = service.preview_for_input(
                raw,
                self._source_path,
            )
            if image is not None and not image.isNull():
                self._replace_tikz_block(
                    position,
                    raw,
                    source_line,
                    image,
                )
        return bool(requests)

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
        image_format.setHeight(
            max(float(image.height()) * scale, 1.0)
        )
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
                matching_blocks.append(
                    (block.position(), meta.source_line)
                )
            block = block.next()

        if not matching_blocks:
            return

        for position, source_line in reversed(matching_blocks):
            self._replace_tikz_block(
                position,
                raw,
                source_line,
                QImage(image),
            )
        self.viewport().update()

    def _replace_tikz_block(
        self,
        position: int,
        raw: str,
        source_line: int,
        image: QImage,
    ) -> None:
        document = self.document()
        block = document.findBlock(int(position))
        if not block.isValid():
            return

        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        was_modified = document.isModified()
        try:
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self._insert_tikz_preview(
                cursor,
                raw,
                source_line,
                image,
            )
            document.setModified(was_modified)
        finally:
            self._loading = was_loading

    def _request_inline_math_for_block(self, block) -> None:
        if not block.isValid():
            return
        replacements: list[tuple[int, int, str, QImage]] = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                raw = fragment.charFormat().property(_RAW_LATEX_PROPERTY)
                if raw and self._math_visual_preview_service.is_inline_math(str(raw)):
                    image = self._math_visual_preview_service.request(str(raw))
                    if image is not None and not image.isNull():
                        replacements.append(
                            (
                                fragment.position(),
                                fragment.length(),
                                str(raw),
                                QImage(image),
                            )
                        )
            iterator += 1
        self._replace_inline_math_ranges(replacements)

    def _on_math_preview_ready(self, raw: str, image: object) -> None:
        if not isinstance(image, QImage) or image.isNull():
            return
        if self._math_visual_preview_service.is_inline_math(raw):
            self._replace_matching_inline_math(raw, QImage(image))
        if self._math_visual_preview_service.is_display_math(raw):
            self._replace_matching_math_blocks(raw, QImage(image))
        self.viewport().update()

    def _replace_matching_inline_math(self, raw: str, image: QImage) -> None:
        replacements: list[tuple[int, int, str, QImage]] = []
        block = self.document().firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    value = fragment.charFormat().property(_RAW_LATEX_PROPERTY)
                    if value and str(value) == raw:
                        replacements.append(
                            (
                                fragment.position(),
                                fragment.length(),
                                raw,
                                QImage(image),
                            )
                        )
                iterator += 1
            block = block.next()
        self._replace_inline_math_ranges(replacements)

    def _replace_inline_math_ranges(
        self,
        replacements: list[tuple[int, int, str, QImage]],
    ) -> None:
        if not replacements:
            return
        document = self.document()
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        was_modified = document.isModified()
        try:
            for position, length, raw, image in sorted(
                replacements,
                key=lambda item: item[0],
                reverse=True,
            ):
                cursor = QTextCursor(document)
                cursor.setPosition(position)
                cursor.setPosition(
                    position + max(length, 1),
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.removeSelectedText()
                self._insert_inline_math_image(cursor, raw, image)
            document.setModified(was_modified)
        finally:
            self._loading = was_loading

    def _insert_inline_math_image(
        self,
        cursor: QTextCursor,
        raw: str,
        image: QImage,
    ) -> None:
        digest = sha256(
            f"inline:{raw}:{image.cacheKey()}".encode("utf-8")
        ).hexdigest()[:20]
        key = QUrl(f"ndmath-inline:{digest}")
        self.document().addResource(
            QTextDocument.ResourceType.ImageResource,
            key,
            image,
        )
        height = max(float(self.fontMetrics().height()) * 1.35, 18.0)
        scale = height / max(float(image.height()), 1.0)
        width = max(float(image.width()) * scale, 1.0)
        width = min(width, float(max(self.viewport().width() - 80, 80)))
        image_format = QTextImageFormat()
        image_format.setName(key.toString())
        image_format.setWidth(width)
        image_format.setHeight(height)
        image_format.setProperty(_RAW_LATEX_PROPERTY, raw)
        cursor.insertImage(image_format)

    def _insert_math_preview(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int,
        image: QImage,
    ) -> None:
        digest = sha256(
            f"block:{raw}:{image.cacheKey()}".encode("utf-8")
        ).hexdigest()[:20]
        key = QUrl(f"ndmath-block:{digest}")
        self.document().addResource(
            QTextDocument.ResourceType.ImageResource,
            key,
            image,
        )
        available = max(self.viewport().width() - 110, 220)
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
                display="Math preview",
                source_line=source_line,
            )
        )
        block_format = cursor.blockFormat()
        block_format.setTopMargin(6)
        block_format.setBottomMargin(6)
        block_format.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cursor.setBlockFormat(block_format)
        cursor.insertImage(image_format)

    def _replace_matching_math_blocks(self, raw: str, image: QImage) -> None:
        matching: list[tuple[int, int]] = []
        block = self.document().firstBlock()
        while block.isValid():
            meta = block.userData()
            if (
                isinstance(meta, _BlockMeta)
                and meta.kind == "raw"
                and meta.raw == raw
            ):
                matching.append((block.position(), meta.source_line))
            block = block.next()
        for position, source_line in reversed(matching):
            self._replace_math_block(position, raw, source_line, image)

    def _replace_math_block(
        self,
        position: int,
        raw: str,
        source_line: int,
        image: QImage,
    ) -> None:
        document = self.document()
        block = document.findBlock(int(position))
        if not block.isValid():
            return
        was_loading = self._loading
        self._loading = True
        self._emit_timer.stop()
        was_modified = document.isModified()
        try:
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self._insert_math_preview(cursor, raw, source_line, image)
            document.setModified(was_modified)
        finally:
            self._loading = was_loading

    def keyPressEvent(self, event) -> None:
        modifiers = event.modifiers()
        control = bool(
            modifiers & Qt.KeyboardModifier.ControlModifier
        )
        shift = bool(
            modifiers & Qt.KeyboardModifier.ShiftModifier
        )
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
            next_meta = self._copy_block_meta(
                next_block.userData()
            )
            next_format = QTextBlockFormat(
                next_block.blockFormat()
            )
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
                edit.select(
                    QTextCursor.SelectionType.Document
                )
        edit.removeSelectedText()
        survivor = document.findBlock(start)
        if survivor.isValid():
            survivor.setUserData(next_meta)
            format_cursor = QTextCursor(survivor)
            format_cursor.setBlockFormat(
                next_format
                if next_format is not None
                else QTextBlockFormat()
            )
        edit.endEditBlock()
        restored = QTextCursor(document)
        restored.setPosition(
            min(
                max(start, 0),
                max(
                    document.characterCount() - 1,
                    0,
                ),
            )
        )
        self.setTextCursor(restored)
        self.ensureCursorVisible()

    @staticmethod
    def _copy_block_meta(
        data,
    ) -> _BlockMeta | None:
        if not isinstance(data, _BlockMeta):
            return None
        return _BlockMeta(
            kind=data.kind,
            command=data.command,
            raw=data.raw,
            display=data.display,
            depth=data.depth,
            source_line=data.source_line,
            source_segments=list(
                data.source_segments
            ),
        )
