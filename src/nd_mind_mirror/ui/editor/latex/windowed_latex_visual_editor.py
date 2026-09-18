"""Canonical windowed Visual LaTeX editor."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QImage,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
)

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import (
    _BlockMeta,
    _RAW_LATEX_PROPERTY,
)
from nd_mind_mirror.ui.editor.latex.visual.windowed_latex_visual_editor_with_resources import (
    WindowedLatexVisualEditor as ResourceWindowedLatexVisualEditor,
)


class WindowedLatexVisualEditor(ResourceWindowedLatexVisualEditor):
    """Preload math and refresh only the TikZ resource that actually changed."""

    def load_source(
        self,
        source: str,
        source_path: str | Path | None = None,
    ) -> None:
        self._math_visual_preview_service.preload_display_math(str(source))
        super().load_source(source, source_path)

    def refresh_tikz_path(
        self,
        changed_path: str | Path,
        *,
        allow_fallback: bool = False,
    ) -> bool:
        """Refresh only blocks that reference ``changed_path``."""
        service = self._tikz_visual_preview_service
        if service is None or self._source_path is None:
            return False

        target = Path(changed_path).expanduser().resolve(strict=False)
        requests: list[tuple[int, str, int]] = []
        block = self.document().firstBlock()
        while block.isValid():
            meta = block.userData()
            if (
                isinstance(meta, _BlockMeta)
                and meta.kind == "raw"
                and self._TIKZ_INPUT.match(meta.raw.strip()) is not None
            ):
                resolved = service.target_for_input(meta.raw, self._source_path)
                if resolved is not None and resolved == target:
                    requests.append(
                        (
                            block.position(),
                            meta.raw,
                            meta.source_line,
                        )
                    )
            block = block.next()

        for position, raw, source_line in reversed(requests):
            image = service.preview_for_input(
                raw,
                self._source_path,
                allow_fallback=bool(allow_fallback),
            )
            if image is None or image.isNull():
                continue
            self._replace_tikz_block(
                position,
                raw,
                source_line,
                image,
            )

        if requests:
            self.viewport().update()
        return bool(requests)

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
        width, height = self._math_visual_preview_service.logical_size(
            raw,
            image,
            display=False,
        )
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
        width, height = self._math_visual_preview_service.logical_size(
            raw,
            image,
            display=True,
        )
        image_format = QTextImageFormat()
        image_format.setName(key.toString())
        image_format.setWidth(width)
        image_format.setHeight(height)
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
