import os
from pathlib import Path

from PySide6.QtCore import QMimeData


class ImageMimeReferenceResolver:
    """Resolve dragged local image files without creating duplicate assets."""

    _IMAGE_SUFFIXES = {
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".webp",
        ".gif",
    }

    def local_image_path(
        self,
        mime_data: QMimeData,
    ) -> Path | None:
        if not mime_data.hasUrls():
            return None

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            candidate = Path(url.toLocalFile()).expanduser()
            try:
                candidate = candidate.resolve(strict=True)
            except OSError:
                continue

            if (
                candidate.is_file()
                and candidate.suffix.lower() in self._IMAGE_SUFFIXES
            ):
                return candidate

        return None

    def latex_reference_path(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> Path | None:
        image_path = self.local_image_path(mime_data)
        if image_path is None:
            return None

        source_path = Path(tex_path).expanduser().resolve()
        source_directory = source_path.parent
        relative_path = Path(
            os.path.relpath(image_path, start=source_directory)
        )

        # Keep a lexical path rooted at the TeX directory. LatexEditor already
        # calls relative_to(source_directory), so ../ components remain intact
        # while the path still points to the original dragged file.
        return source_directory / relative_path
