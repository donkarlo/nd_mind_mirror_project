"""Readable sizing policy for rendered LaTeX Source-mode previews."""

from __future__ import annotations


class SourceLatexPreviewSizePolicy:
    """Compute stable logical dimensions for formula and table preview images."""

    _TABLE_DISPLAY_DIVISOR = 1.55
    _TABLE_MIN_AVAILABLE_RATIO = 0.58
    _TABLE_MAX_AVAILABLE_RATIO = 0.96
    _TABLE_MIN_WIDTH_PX = 320
    _DISPLAY_MATH_RASTER_DIVISOR = 1.90
    _DISPLAY_MATH_MAX_AVAILABLE_RATIO = 0.94

    @classmethod
    def logical_size(
        cls,
        *,
        image_width: int,
        image_height: int,
        kind: str,
        display: bool,
        line_height: int,
        available: int,
    ) -> tuple[int, int]:
        """Return readable preview dimensions while preserving the image aspect ratio."""
        image_width = max(int(image_width), 1)
        image_height = max(int(image_height), 1)
        available = max(int(available), 1)
        line_height = max(int(line_height), 1)
        ratio = float(image_width) / float(image_height)

        if kind == "table":
            maximum = max(int(round(available * cls._TABLE_MAX_AVAILABLE_RATIO)), 1)
            minimum = min(
                max(
                    cls._TABLE_MIN_WIDTH_PX,
                    int(round(available * cls._TABLE_MIN_AVAILABLE_RATIO)),
                ),
                maximum,
            )
            natural = max(
                int(round(image_width / cls._TABLE_DISPLAY_DIVISOR)),
                1,
            )
            target_width = min(max(natural, minimum), maximum)
            return target_width, max(int(round(target_width / ratio)), 1)

        if display:
            minimum_height = max(int(round(line_height * 2.15)), 42)
            minimum_width = max(int(round(minimum_height * ratio)), 1)
            natural_width = max(
                int(round(image_width / cls._DISPLAY_MATH_RASTER_DIVISOR)),
                1,
            )
            maximum = max(
                int(round(available * cls._DISPLAY_MATH_MAX_AVAILABLE_RATIO)),
                1,
            )
            target_width = min(
                max(natural_width, minimum_width),
                maximum,
            )
            target_height = max(int(round(target_width / ratio)), 1)
            return target_width, target_height

        target_height = max(int(round(line_height * 1.12)), 18)
        target_width = max(int(round(target_height * ratio)), 1)
        target_width = min(target_width, max(int(available * 0.45), 40))
        target_height = max(int(round(target_width / ratio)), 1)
        return target_width, target_height
