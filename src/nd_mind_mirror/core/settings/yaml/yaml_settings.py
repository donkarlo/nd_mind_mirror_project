from pathlib import Path
from typing import Any

import yaml


class YamlSettings:
    def __init__(
        self,
        settings_path: str | Path | None = None,
    ) -> None:
        self._project_root = self._find_project_root()
        self._settings_path = (
            Path(settings_path).expanduser().resolve()
            if settings_path is not None
            else self._project_root / "settings.yaml"
        )
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
    def editor_font_family(self) -> str:
        return str(
            self._get("editor", "font_family", default="")
        ).strip()

    @property
    def editor_font_size(self) -> int:
        return self._positive_int(
            self._get("editor", "font_size", default=11),
            11,
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
                default=120,
            ),
            120,
        )
        return max(60, min(value, 300))

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
    def editor_indent_size(self) -> int:
        return self._positive_int(
            self._get("editor", "indent_size", default=4),
            4,
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
            candidate = self._project_root / candidate

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
    def preview_latex_template_path(self) -> Path:
        raw = str(
            self._get(
                "preview",
                "latex_template_path",
                default="resources/latex_preview_template.tex",
            )
        ).strip()

        candidate = Path(
            raw or "resources/latex_preview_template.tex"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

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
                default="resources/latex_preview_beamer_template.tex",
            )
        ).strip()

        candidate = Path(
            raw or "resources/latex_preview_beamer_template.tex"
        ).expanduser()

        if not candidate.is_absolute():
            candidate = self._project_root / candidate

        try:
            return candidate.resolve()
        except OSError:
            return candidate.absolute()

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
