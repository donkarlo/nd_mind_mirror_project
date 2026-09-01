"""Resolve trustworthy backgrounds for graphic documents opened on the iPad."""

from __future__ import annotations

import base64
from typing import Any

from PySide6.QtGui import QImage


class GraphicDocumentBackgroundResolver:
    """Choose a reliable raster background without mutating stored sidecar data."""

    _MIN_EXISTING_INFORMATION = 0.008
    _NEAR_WHITE_INFORMATION = 0.002
    _RELATIVE_INFORMATION_LIMIT = 0.12

    def resolve_for_open(
        self,
        document: dict[str, Any],
        paired_image_base64: str,
    ) -> tuple[dict[str, Any], bool]:
        """Return an iPad-safe document and whether the paired image was recovered."""
        resolved = dict(document)
        paired_image = self.decode_base64_image(paired_image_base64)
        if paired_image is None:
            return resolved, False

        stored_background_base64 = str(
            document.get("background_image_base64", "") or ""
        )
        stored_background = self.decode_base64_image(stored_background_base64)
        if not self._should_recover_from_paired_image(
            stored_background,
            paired_image,
        ):
            return resolved, False

        resolved["background_image_base64"] = paired_image_base64

        # The paired PNG is already the authoritative flattened visual result.
        # Legacy editable layers must not be drawn again over those same pixels.
        drawing = str(document.get("drawing_data_base64", "") or "")
        image_objects = document.get("image_objects")
        has_image_objects = isinstance(image_objects, list) and bool(image_objects)
        if drawing or has_image_objects:
            resolved["drawing_data_base64"] = ""
            resolved["image_objects"] = []

        return resolved, True

    def decode_base64_image(self, encoded: str) -> QImage | None:
        """Decode a base64 raster image, returning None for invalid data."""
        if not encoded:
            return None
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return None
        image = QImage.fromData(raw)
        if image.isNull():
            return None
        return image

    def informative_pixel_fraction(self, image: QImage) -> float:
        """Estimate the visible non-white information contained in an image."""
        if image.isNull():
            return 0.0
        sample = image.scaled(96, 96)
        if sample.isNull() or sample.width() <= 0 or sample.height() <= 0:
            return 0.0

        informative = 0
        total = sample.width() * sample.height()
        for y in range(sample.height()):
            for x in range(sample.width()):
                color = sample.pixelColor(x, y)
                if (
                    color.alpha() >= 16
                    and min(color.red(), color.green(), color.blue()) < 242
                ):
                    informative += 1
        return informative / max(total, 1)

    def is_suspicious_blank_replacement(
        self,
        candidate: QImage,
        existing: QImage,
    ) -> bool:
        """Return True when a new render is nearly white but the existing image is not."""
        candidate_fraction = self.informative_pixel_fraction(candidate)
        existing_fraction = self.informative_pixel_fraction(existing)
        return (
            existing_fraction >= self._MIN_EXISTING_INFORMATION
            and candidate_fraction < self._NEAR_WHITE_INFORMATION
            and candidate_fraction
            < existing_fraction * self._RELATIVE_INFORMATION_LIMIT
        )

    def _should_recover_from_paired_image(
        self,
        stored_background: QImage | None,
        paired_image: QImage,
    ) -> bool:
        paired_fraction = self.informative_pixel_fraction(paired_image)
        if paired_fraction < self._MIN_EXISTING_INFORMATION:
            return False
        if stored_background is None:
            return True

        stored_fraction = self.informative_pixel_fraction(stored_background)
        return (
            stored_fraction < self._NEAR_WHITE_INFORMATION
            and stored_fraction < paired_fraction * self._RELATIVE_INFORMATION_LIMIT
        )
