from pathlib import Path

from PySide6.QtCore import QMimeData
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.core.clipboard.file_clipboard_mime_data_controller import (
    FileClipboardMimeDataController,
)
from nd_mind_mirror.core.clipboard.file_system_clipboard_controller import (
    FileSystemClipboardController,
)
from nd_mind_mirror.core.clipboard.image.image_mime_reference_resolver import (
    ImageMimeReferenceResolver,
)


class ClipboardImageSaver:
    def __init__(self) -> None:
        self._reference_resolver = ImageMimeReferenceResolver()
        self._file_system_clipboard_controller = (
            FileSystemClipboardController.install_once(
                QApplication.instance()
            )
        )

    def latex_reference_paths(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> list[Path]:
        """Return all original local image references carried by the MIME data."""
        return self._reference_resolver.latex_reference_paths(
            mime_data,
            tex_path,
        )

    def save(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> Path | None:
        reference_path = self._reference_resolver.latex_reference_path(
            mime_data,
            tex_path,
        )
        if reference_path is not None:
            return reference_path

        image = self._extract_embedded_image(mime_data)

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
        """Save one real pixel clipboard image, never a copied local file URL."""
        controller = self._file_system_clipboard_controller
        if controller is not None and controller.has_active_copy:
            return None

        if FileClipboardMimeDataController.local_paths(mime_data):
            return None

        image = self._extract_embedded_image(mime_data)
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

    @staticmethod
    def _extract_embedded_image(
        mime_data: QMimeData,
    ) -> QImage | None:
        if not mime_data.hasImage():
            return None

        image_data = mime_data.imageData()
        if isinstance(image_data, QImage):
            return image_data
        if isinstance(image_data, QPixmap):
            return image_data.toImage()
        return None

    def _extract_image(
        self,
        mime_data: QMimeData,
    ) -> QImage | None:
        """Return image pixels without raising on ordinary text MIME data."""
        embedded = self._extract_embedded_image(mime_data)
        if embedded is not None:
            return embedded

        local_image_path = self._reference_resolver.local_image_path(mime_data)
        if local_image_path is None:
            return None

        image = QImage(str(local_image_path))
        if image.isNull():
            return None
        return image
