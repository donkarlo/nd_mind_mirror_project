from pathlib import Path
from typing import Any

import yaml

from nd_mind_mirror.core.settings.storage.settings_storage import SettingsStorage


class YamlSettings:
    def __init__(
        self,
        settings_path: str | Path | None = None,
    ) -> None:
        self._project_root = self._find_project_root()
        self._storage = SettingsStorage(self._project_root)
        if settings_path is None:
            self._storage.prepare()
            self._settings_path = self._storage.settings_path.resolve()
        else:
            self._settings_path = Path(settings_path).expanduser().resolve()
        self._data: dict[str, Any] = {}
        self._last_reload_error: str | None = None
        self.reload()

    @property
    def last_reload_error(self) -> str | None:
        return self._last_reload_error

    @property
    def settings_path(self) -> Path:
        return self._settings_path

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def data_root(self) -> Path:
        return self._storage.data_root.resolve()

    @property
    def session_settings_path(self) -> Path:
        return self._storage.session_path.resolve()

    @property
    def ui_state_path(self) -> Path:
        return self._storage.ui_state_path.resolve()

    def migrate_legacy_ui_state(self, legacy_path: str | Path) -> None:
        self._storage.migrate_legacy_ui_state(
            Path(legacy_path).expanduser()
        )

    @property
    def editor_font_family(self) -> str:
        return str(
            self._get("editor", "font_family", default="")
        ).strip()

    @property
    def editor_source_font_size(self) -> int:
        return self._positive_int(
            self._get(
                "editor",
                "source_font_size",
                default=self._get("editor", "font_size", default=16),
            ),
            16,
        )

    @property
    def editor_font_size(self) -> int:
        """Backward-compatible alias for the Source editor font size."""
        return self.editor_source_font_size

    @property
    def editor_visual_font_size(self) -> int:
        """Base font size used only by the LaTeX Visual editor."""
        return self._positive_int(
            self._get(
                "editor",
                "visual_font_size",
                default=self.editor_font_size,
            ),
            self.editor_font_size,
        )

    @property
    def editor_font_min_size(self) -> int:
        return self._positive_int(
            self._get("editor", "font_min_size", default=6),
            6,
        )

    @property
    def editor_font_max_size(self) -> int:
        value = self._positive_int(
            self._get("editor", "font_max_size", default=40),
            40,
        )
        return max(value, self.editor_font_min_size)

    @property
    def editor_line_height_percent(self) -> int:
        value = self._positive_int(
            self._get(
                "editor",
                "line_height_percent",
                default=200,
            ),
            200,
        )
        return max(60, min(value, 300))

    @property
    def editor_visual_line_height_percent(self) -> int:
        """Line height used only by the LaTeX Visual editor."""
        value = self._positive_int(
            self._get(
                "editor",
                "visual_line_height_percent",
                default=self.editor_line_height_percent,
            ),
            self.editor_line_height_percent,
        )
        return max(60, min(value, 300))

    @property
    def editor_source_padding_top(self) -> int:
        return self._non_negative_int(
            self._get("editor", "source_padding_top", default=10),
            10,
        )

    @property
    def editor_source_padding_left(self) -> int:
        return self._non_negative_int(
            self._get("editor", "source_padding_left", default=10),
            10,
        )

    @property
    def editor_source_padding_right(self) -> int:
        return self._non_negative_int(
            self._get("editor", "source_padding_right", default=10),
            10,
        )

    @property
    def editor_visual_padding_top(self) -> int:
        return self._non_negative_int(
            self._get("editor", "visual_padding_top", default=14),
            14,
        )

    @property
    def editor_visual_padding_left(self) -> int:
        return self._non_negative_int(
            self._get("editor", "visual_padding_left", default=16),
            16,
        )

    @property
    def editor_visual_padding_right(self) -> int:
        return self._non_negative_int(
            self._get("editor", "visual_padding_right", default=16),
            16,
        )

    @property
    def editor_visual_update_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get("editor", "visual_update_debounce_ms", default=180),
                180,
            ),
            60,
        )

    @property
    def editor_visual_large_document_threshold_chars(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "editor",
                    "visual_large_document_threshold_chars",
                    default=120000,
                ),
                120000,
            ),
            10000,
        )

    @property
    def editor_visual_large_document_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "editor",
                    "visual_large_document_debounce_ms",
                    default=650,
                ),
                650,
            ),
            self.editor_visual_update_debounce_ms,
        )

    @property
    def editor_latex_text_direction(self) -> str:
        value = str(
            self._get(
                "editor",
                "latex_text_direction",
                default="auto",
            )
        ).strip().casefold()
        return value if value in {"auto", "rtl", "ltr"} else "auto"

    @property
    def editor_latex_rtl_persian_ratio(self) -> float:
        return self._bounded_float(
            self._get(
                "editor",
                "latex_rtl_persian_ratio",
                default=0.35,
            ),
            default=0.35,
            minimum=0.05,
            maximum=0.95,
        )

    @property
    def editor_max_open_tabs(self) -> int:
        value = self._positive_int(
            self._get(
                "editor",
                "max_open_tabs",
                default=20,
            ),
            20,
        )
        return max(1, min(value, 100))

    @property
    def editor_tab_size(self) -> int:
        """Visual/source indentation width shared by all source editors."""
        raw = self._get(
            "editor",
            "tab_size",
            default=self._get("editor", "indent_size", default=4),
        )
        value = self._positive_int(raw, 4)
        return max(1, min(value, 16))

    @property
    def editor_indent_size(self) -> int:
        """Backward-compatible alias for the shared tab size."""
        return self.editor_tab_size

    @property
    def editor_indent_guides_enabled(self) -> bool:
        return self._bool(
            self._get("editor", "indent_guides_enabled", default=True),
            True,
        )

    @property
    def editor_indent_guide_color(self) -> str:
        return str(
            self._get(
                "editor",
                "indent_guide_color",
                default="#d0d0d0",
            )
        ).strip() or "#d0d0d0"

    @property
    def editor_indent_guide_width(self) -> float:
        return self._bounded_float(
            self._get(
                "editor",
                "indent_guide_width",
                default=1.0,
            ),
            default=1.0,
            minimum=0.5,
            maximum=3.0,
        )

    @property
    def editor_cursor_width(self) -> int:
        return self._positive_int(
            self._get("editor", "cursor_width", default=2),
            2,
        )

    @property
    def editor_cursor_flash_time_ms(self) -> int:
        return self._positive_int(
            self._get(
                "editor",
                "cursor_flash_time_ms",
                default=650,
            ),
            650,
        )

    @property
    def editor_soft_wrap(self) -> bool:
        return self._bool(
            self._get("editor", "soft_wrap", default=True),
            True,
        )

    @property
    def editor_wrap_marker(self) -> str:
        value = str(
            self._get("editor", "wrap_marker", default="↳")
        )
        return value if value else "↳"

    @property
    def editor_wrap_marker_color(self) -> str:
        return str(
            self._get(
                "editor",
                "wrap_marker_color",
                default="#9aa0a6",
            )
        ).strip() or "#9aa0a6"

    @property
    def editor_wrap_marker_margin(self) -> int:
        return self._non_negative_int(
            self._get(
                "editor",
                "wrap_marker_margin",
                default=18,
            ),
            18,
        )

    @property
    def editor_current_line_highlight(self) -> str:
        return str(
            self._get(
                "editor",
                "current_line_highlight",
                default="#eaf4ff",
            )
        ).strip() or "#eaf4ff"

    @property
    def latex_shortcuts_file_path(self) -> Path:
        raw = str(
            self._get(
                "completion",
                "latex_shortcuts_file",
                default="latex_shortcuts.yaml",
            )
        ).strip()

        candidate = Path(
            raw or "latex_shortcuts.yaml"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._settings_path.parent / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    @property
    def shortcut_min_prefix_length(self) -> int:
        value = self._positive_int(
            self._get(
                "completion",
                "shortcut_min_prefix_length",
                default=2,
            ),
            2,
        )
        return max(1, min(value, 12))

    @property
    def autosave_enabled(self) -> bool:
        return self._bool(
            self._get("autosave", "enabled", default=True),
            True,
        )

    @property
    def autosave_interval_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "autosave",
                    "interval_ms",
                    default=1000,
                ),
                1000,
            ),
            250,
        )

    @property
    def external_file_sync_enabled(self) -> bool:
        return self._bool(
            self._get(
                "external_file_sync",
                "enabled",
                default=True,
            ),
            True,
        )

    @property
    def external_file_sync_interval_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "external_file_sync",
                    "interval_ms",
                    default=1000,
                ),
                1000,
            ),
            250,
        )

    @property
    def search_default_path(self) -> Path:
        raw = str(
            self._get(
                "search",
                "default_path",
                default=str(Path.home()),
            )
        ).strip()

        candidate = Path(raw or str(Path.home())).expanduser()

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    @property
    def search_ignore_file_path(self) -> Path:
        raw = str(
            self._get(
                "search",
                "ignore_file",
                default="search_ignore.yaml",
            )
        ).strip()

        candidate = Path(
            raw or "search_ignore.yaml"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._settings_path.parent / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    @property
    def search_max_results(self) -> int:
        return self._positive_int(
            self._get("search", "max_results", default=1000),
            1000,
        )

    @property
    def search_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get("search", "debounce_ms", default=180),
                180,
            ),
            50,
        )

    @property
    def search_fuzzy_threshold(self) -> float:
        return self._bounded_float(
            self._get(
                "search",
                "fuzzy_threshold",
                default=0.86,
            ),
            default=0.86,
            minimum=0.25,
            maximum=0.95,
        )

    @property
    def search_window_width(self) -> int:
        return max(
            self._positive_int(
                self._get("search", "window_width", default=900),
                900,
            ),
            420,
        )

    @property
    def search_window_height(self) -> int:
        return max(
            self._positive_int(
                self._get("search", "window_height", default=620),
                620,
            ),
            320,
        )

    @property
    def search_tree_indent_width(self) -> int:
        return self._positive_int(
            self._get(
                "search",
                "tree_indent_width",
                default=10,
            ),
            10,
        )

    @property
    def search_hierarchical_path_matching(self) -> bool:
        return self._bool(
            self._get(
                "search",
                "hierarchical_path_matching",
                default=True,
            ),
            True,
        )

    @property
    def preview_default_zoom_percent(self) -> int:
        value = self._positive_int(
            self._get(
                "preview",
                "default_zoom_percent",
                default=100,
            ),
            100,
        )
        return max(20, min(value, 500))

    @property
    def preview_auto_fit_on_open(self) -> bool:
        return self._bool(
            self._get(
                "preview",
                "auto_fit_on_open",
                default=True,
            ),
            True,
        )

    @property
    def preview_fit_width_percent(self) -> int:
        value = self._positive_int(
            self._get(
                "preview",
                "fit_width_percent",
                default=95,
            ),
            95,
        )
        return max(50, min(value, 100))

    @property
    def preview_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "preview",
                    "debounce_ms",
                    default=220,
                ),
                220,
            ),
            50,
        )

    @property
    def preview_large_document_threshold_chars(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "preview",
                    "large_document_threshold_chars",
                    default=120000,
                ),
                120000,
            ),
            10000,
        )

    @property
    def preview_large_document_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "preview",
                    "large_document_debounce_ms",
                    default=650,
                ),
                650,
            ),
            self.preview_debounce_ms,
        )

    @property
    def preview_cursor_sync_enabled(self) -> bool:
        return self._bool(
            self._get(
                "preview",
                "cursor_sync_enabled",
                default=True,
            ),
            True,
        )

    @property
    def preview_cursor_sync_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "preview",
                    "cursor_sync_debounce_ms",
                    default=120,
                ),
                120,
            ),
            30,
        )

    @property
    def graphic_directory_name(self) -> str:
        value = str(self._get("graphic", "directory", default=".")).strip()
        return value.strip("/\\") or "."

    @property
    def graphic_width_ratio(self) -> float:
        return self._bounded_float(
            self._get("graphic", "latex_width_ratio", default=0.90),
            default=0.90,
            minimum=0.10,
            maximum=1.0,
        )

    @property
    def graphic_canvas_width(self) -> int:
        return max(self._positive_int(self._get("graphic", "canvas_width", default=1600), 1600), 64)

    @property
    def graphic_canvas_height(self) -> int:
        return max(self._positive_int(self._get("graphic", "canvas_height", default=1000), 1000), 64)

    @property
    def graphic_bridge_http_url(self) -> str:
        return str(
            self._get("graphic", "bridge_http_url", default="http://127.0.0.1:8766")
        ).strip()

    @property
    def graphic_bridge_token(self) -> str:
        return str(self._get("graphic", "bridge_token", default="")).strip()

    @property
    def preview_edit_location_highlight_enabled(self) -> bool:
        return self._bool(
            self._get(
                "preview",
                "edit_location_highlight_enabled",
                default=True,
            ),
            True,
        )

    @property
    def preview_edit_location_highlight_debounce_ms(self) -> int:
        return max(
            self._positive_int(
                self._get(
                    "preview",
                    "edit_location_highlight_debounce_ms",
                    default=220,
                ),
                220,
            ),
            100,
        )

    @property
    def preview_latex_template_path(self) -> Path:
        raw = str(
            self._get(
                "preview",
                "latex_template_path",
                default="templates/latex_preview_template.tex",
            )
        ).strip()

        candidate = Path(
            raw or "templates/latex_preview_template.tex"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._settings_path.parent / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    @property
    def preview_latex_beamer_template_path(self) -> Path:
        raw = str(
            self._get(
                "preview",
                "latex_beamer_template_path",
                default="templates/latex_preview_beamer_template.tex",
            )
        ).strip()

        candidate = Path(
            raw or "templates/latex_preview_beamer_template.tex"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._settings_path.parent / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

    @property
    def new_latex_file_templates(self) -> list[tuple[str, Path]]:
        section = self._data.get("new_latex_file", {})
        raw_templates = section.get("templates", {}) if isinstance(section, dict) else {}
        result: list[tuple[str, Path]] = []
        if isinstance(raw_templates, dict):
            for label, raw_path in raw_templates.items():
                label_text = str(label).strip()
                path_text = str(raw_path).strip()
                if not label_text or not path_text:
                    continue
                candidate = Path(path_text).expanduser()
                if not candidate.is_absolute():
                    candidate = self._settings_path.parent / candidate
                try:
                    candidate = candidate.resolve()
                except OSError:
                    candidate = candidate.absolute()
                result.append((label_text, candidate))
        if result:
            return result
        return [
            ("Article (standard)", self.preview_latex_template_path),
            ("Beamer", self.preview_latex_beamer_template_path),
        ]

    @property
    def preview_shell_escape(self) -> bool:
        return self._bool(
            self._get(
                "preview",
                "shell_escape",
                default=True,
            ),
            True,
        )

    @property
    def double_shift_interval_ms(self) -> int:
        return self._positive_int(
            self._get(
                "input",
                "double_shift_interval_ms",
                default=450,
            ),
            450,
        )

    @property
    def splitter_handle_width(self) -> int:
        return self._positive_int(
            self._get(
                "ui",
                "splitter_handle_width",
                default=9,
            ),
            9,
        )

    @property
    def navigator_indent_width(self) -> int:
        return self._positive_int(
            self._get(
                "ui",
                "navigator_indent_width",
                default=10,
            ),
            10,
        )

    @property
    def navigator_row_height(self) -> int:
        value = self._positive_int(
            self._get(
                "ui",
                "navigator_row_height",
                default=24,
            ),
            24,
        )
        return max(18, min(value, 60))

    def reload(self) -> bool:
        try:
            loaded = yaml.safe_load(
                self._settings_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError) as exc:
            self._last_reload_error = str(exc)
            return False

        if not isinstance(loaded, dict):
            self._last_reload_error = (
                "settings.yaml must contain a YAML mapping at the top level."
            )
            return False

        self._data = loaded
        self._last_reload_error = None
        return True

    def _get(
        self,
        section: str,
        key: str,
        default: Any,
    ) -> Any:
        section_data = self._data.get(section, {})

        if not isinstance(section_data, dict):
            return default

        return section_data.get(key, default)

    def _positive_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default

        return parsed if parsed > 0 else default

    def _non_negative_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default

        return parsed if parsed >= 0 else default

    def _bounded_float(
        self,
        value: Any,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default

        return max(minimum, min(parsed, maximum))

    def _bool(
        self,
        value: Any,
        default: bool,
    ) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "yes", "1", "on"}:
                return True
            if normalized in {"false", "no", "0", "off"}:
                return False

        if isinstance(value, (int, float)):
            return bool(value)

        return default

    def _find_project_root(self) -> Path:
        current = Path(__file__).resolve()

        for parent in current.parents:
            if (parent / "pyproject.toml").is_file():
                return parent

        return Path.cwd().resolve()
