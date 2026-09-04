from __future__ import annotations

from pathlib import Path

import yaml


class VisualWindowSettings:
    """Validated Visual-window configuration loaded from the active settings file."""

    def __init__(
        self,
        *,
        large_document_threshold_chars: int,
        pages_above: int,
        pages_below: int,
        estimated_chars_per_page: int,
        min_lines_per_page: int,
        max_lines_per_page: int,
        rewindow_delay_ms: int,
        scroll_edge_ratio: float,
    ) -> None:
        self.large_document_threshold_chars = max(
            int(large_document_threshold_chars),
            10_000,
        )
        self.pages_above = max(int(pages_above), 0)
        self.pages_below = max(int(pages_below), 0)
        self.estimated_chars_per_page = max(
            int(estimated_chars_per_page),
            400,
        )
        self.min_lines_per_page = max(int(min_lines_per_page), 4)
        self.max_lines_per_page = max(
            int(max_lines_per_page),
            self.min_lines_per_page,
        )
        self.rewindow_delay_ms = max(int(rewindow_delay_ms), 40)
        self.scroll_edge_ratio = max(
            0.05,
            min(float(scroll_edge_ratio), 0.35),
        )

    @property
    def target_window_chars(self) -> int:
        page_count = self.pages_above + self.pages_below + 1
        return max(
            page_count * self.estimated_chars_per_page,
            8_000,
        )

    @property
    def hard_window_chars(self) -> int:
        # The hard cap prevents a long prose paragraph/environment from turning
        # Visual virtualization back into a multi-megabyte QTextDocument load.
        return min(
            max(self.target_window_chars * 2, 16_000),
            96_000,
        )

    @classmethod
    def from_app_settings(cls, app_settings) -> "VisualWindowSettings":
        data = cls._load_editor_mapping(app_settings.settings_path)
        return cls(
            large_document_threshold_chars=(
                app_settings.editor_visual_large_document_threshold_chars
            ),
            pages_above=cls._positive_int(
                data.get("visual_window_pages_above"),
                4,
                allow_zero=True,
            ),
            pages_below=cls._positive_int(
                data.get("visual_window_pages_below"),
                4,
                allow_zero=True,
            ),
            estimated_chars_per_page=cls._positive_int(
                data.get("visual_window_estimated_chars_per_page"),
                2400,
            ),
            min_lines_per_page=cls._positive_int(
                data.get(
                    "visual_window_min_lines_per_page",
                    data.get("visual_window_min_lines_per_peage"),
                ),
                12,
            ),
            max_lines_per_page=cls._positive_int(
                data.get("visual_window_max_lines_per_page"),
                45,
            ),
            rewindow_delay_ms=cls._positive_int(
                data.get("visual_window_rewindow_delay_ms"),
                90,
            ),
            scroll_edge_ratio=cls._float(
                data.get("visual_window_scroll_edge_ratio"),
                0.14,
            ),
        )

    @staticmethod
    def _load_editor_mapping(settings_path: str | Path) -> dict[str, object]:
        try:
            raw = yaml.safe_load(
                Path(settings_path).expanduser().read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError):
            return {}
        if not isinstance(raw, dict):
            return {}
        editor = raw.get("editor", {})
        return editor if isinstance(editor, dict) else {}

    @staticmethod
    def _positive_int(value, default: int, allow_zero: bool = False) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            return int(default)
        minimum = 0 if allow_zero else 1
        return result if result >= minimum else int(default)

    @staticmethod
    def _float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)
