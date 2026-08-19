from pathlib import Path

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage, QPixmap


class ClipboardImageSaver:
    def save(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> Path | None:
        image = self._extract_image(mime_data)

        if image is None or image.isNull():
            return None

        source_path = Path(tex_path).expanduser().resolve()
        target_path = source_path.parent / f"{source_path.stem}.png"

        if not image.save(str(target_path), "PNG"):
            return None

        return target_path

    def _extract_image(
        self,
        mime_data: QMimeData,
    ) -> QImage | None:
        if mime_data.hasImage():
            image_data = mime_data.imageData()

            if isinstance(image_data, QImage):
                return image_data

            if isinstance(image_data, QPixmap):
                return image_data.toImage()

        if mime_data.hasUrls():
            for url in mime_data.urls():
                if not url.isLocalFile():
                    continue

                candidate = Path(url.toLocalFile())

                if candidate.suffix.lower() not in {
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".bmp",
                    ".webp",
                    ".gif",
                }:
                    continue

                image = QImage(str(candidate))

                if not image.isNull():
                    return image

        return None
