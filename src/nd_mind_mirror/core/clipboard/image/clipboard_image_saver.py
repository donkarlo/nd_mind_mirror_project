from pathlib import Path

from PySide6.QtCore import QMimeData
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap


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


    def save_to_directory(
        self,
        mime_data: QMimeData,
        directory: str | Path,
        *,
        base_name: str = "img",
        extension: str = ".jpg",
    ) -> Path | None:
        """Save one clipboard image using a collision-safe conventional name."""
        image = self._extract_image(mime_data)
        if image is None or image.isNull():
            return None

        target_directory = Path(directory).expanduser().resolve()
        if not target_directory.is_dir():
            return None

        normalized_extension = extension.lower()
        if normalized_extension not in {".jpg", ".jpeg", ".png"}:
            normalized_extension = ".jpg"

        target_path = self.next_available_path(
            target_directory,
            base_name=base_name,
            extension=normalized_extension,
        )

        output_image = image
        image_format = "PNG"
        if normalized_extension in {".jpg", ".jpeg"}:
            # JPEG has no alpha channel. Composite transparent clipboard
            # pixels onto white so screenshots/diagrams do not turn black.
            flattened = QImage(
                image.size(),
                QImage.Format.Format_RGB32,
            )
            flattened.fill(Qt.GlobalColor.white)
            painter = QPainter(flattened)
            painter.drawImage(0, 0, image)
            painter.end()
            output_image = flattened
            image_format = "JPG"

        if not output_image.save(str(target_path), image_format, 95):
            return None
        return target_path

    @staticmethod
    def next_available_path(
        directory: str | Path,
        *,
        base_name: str = "img",
        extension: str = ".jpg",
    ) -> Path:
        directory_path = Path(directory)
        suffix = extension if extension.startswith(".") else f".{extension}"
        candidate = directory_path / f"{base_name}{suffix}"
        if not candidate.exists():
            return candidate

        counter = 2
        while True:
            candidate = directory_path / f"{base_name}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

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
