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

    def local_image_paths(
        self,
        mime_data: QMimeData,
    ) -> list[Path]:
        """Return every unique local image URL in the original MIME order."""
        if not mime_data.hasUrls():
            return []

        result: list[Path] = []
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
                and candidate not in result
            ):
                result.append(candidate)

        return result

    def local_image_path(
        self,
        mime_data: QMimeData,
    ) -> Path | None:
        paths = self.local_image_paths(mime_data)
        return paths[0] if paths else None

    def latex_reference_paths(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> list[Path]:
        """Return lexical paths rooted at the TeX directory for all image URLs."""
        image_paths = self.local_image_paths(mime_data)
        if not image_paths:
            return []

        source_path = Path(tex_path).expanduser().resolve()
        source_directory = source_path.parent
        references: list[Path] = []
        for image_path in image_paths:
            relative_path = Path(
                os.path.relpath(image_path, start=source_directory)
            )
            references.append(source_directory / relative_path)
        return references

    def latex_reference_path(
        self,
        mime_data: QMimeData,
        tex_path: str | Path,
    ) -> Path | None:
        references = self.latex_reference_paths(mime_data, tex_path)
        return references[0] if references else None
