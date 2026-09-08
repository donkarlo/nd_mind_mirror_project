"""Persist Mind Mirror settings under the Dropbox repo data directory while preserving older user choices."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import shutil
from typing import Any

import yaml


class SettingsStorage:
    """Own persistent user-editable configuration files outside the replaceable application source tree."""

    LEGACY_DATA_ROOT = Path.home() / "Desktop" / "repo" / "data" / "nd_mind_mirror_project"

    def __init__(self, project_root: str | Path) -> None:
        """Resolve the project-relative Dropbox data directory and every persistent settings path."""
        self.project_root = Path(project_root).expanduser().resolve()
        self.data_root = self.project_root.parent / "data" / "nd_mind_mirror_project"
        self.legacy_data_root = self.LEGACY_DATA_ROOT.expanduser()
        self.defaults_root = Path(__file__).resolve().parents[1] / "defaults"
        self.templates_dir = self.data_root / "templates"
        self.settings_path = self.data_root / "settings.yaml"
        self.shortcuts_path = self.data_root / "latex_shortcuts.yaml"
        self.keyboard_shortcuts_path = self.data_root / "keyboard_shortcuts.yaml"
        self.ignore_path = self.data_root / "search_ignore.yaml"
        self.article_template_path = self.templates_dir / "latex_preview_template.tex"
        self.beamer_template_path = self.templates_dir / "latex_preview_beamer_template.tex"
        self.ui_state_path = self.data_root / "ui_state.json"
        self.session_path = self.data_root / "session.ini"

    def prepare(self) -> None:
        """Create or merge all persistent settings while migrating files from the previous Desktop data directory."""
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._prepare_yaml(
            destination=self.settings_path,
            shipped=self.defaults_root / "settings.yaml",
            legacy=self._first_existing(
                self.legacy_data_root / "settings.yaml",
                self.project_root / "settings.yaml",
            ),
            normalize=self._normalize_settings,
        )
        self._prepare_yaml(
            destination=self.shortcuts_path,
            shipped=self.defaults_root / "latex_shortcuts.yaml",
            legacy=self._first_existing(
                self.legacy_data_root / "latex_shortcuts.yaml",
                self.project_root / "latex_shortcuts.yaml",
            ),
        )
        self._prepare_yaml(
            destination=self.keyboard_shortcuts_path,
            shipped=self.defaults_root / "keyboard_shortcuts.yaml",
            legacy=self._first_existing(
                self.legacy_data_root / "keyboard_shortcuts.yaml",
            ),
        )
        self._prepare_yaml(
            destination=self.ignore_path,
            shipped=self.defaults_root / "search_ignore.yaml",
            legacy=self._first_existing(
                self.legacy_data_root / "search_ignore.yaml",
                self.project_root / "search_ignore.yaml",
            ),
        )
        self._prepare_text(
            self.article_template_path,
            self.defaults_root / "templates" / "latex_preview_template.tex",
            legacy=self.legacy_data_root / "templates" / "latex_preview_template.tex",
        )
        self._prepare_text(
            self.beamer_template_path,
            self.defaults_root / "templates" / "latex_preview_beamer_template.tex",
            legacy=self.legacy_data_root / "templates" / "latex_preview_beamer_template.tex",
        )

        self._copy_legacy_file_if_missing(
            self.legacy_data_root / "session.ini",
            self.session_path,
        )
        self._copy_legacy_file_if_missing(
            self.legacy_data_root / "ui_state.json",
            self.ui_state_path,
        )

        if not self.session_path.exists():
            try:
                self.session_path.touch()
            except OSError:
                pass

    def _prepare_yaml(
        self,
        *,
        destination: Path,
        shipped: Path,
        legacy: Path | None = None,
        normalize=None,
    ) -> None:
        """Merge one YAML file so user values win while missing shipped schema entries are added."""
        shipped_data = self._read_yaml(shipped)
        if not isinstance(shipped_data, (dict, list)):
            shipped_data = {}

        existing_data = self._read_yaml(destination)
        if not isinstance(existing_data, (dict, list)):
            existing_data = None
        destination_original = deepcopy(existing_data)

        if existing_data is None and legacy is not None and legacy.exists():
            existing_data = self._read_yaml(legacy)

        if existing_data is None:
            existing_data = deepcopy(shipped_data)

        if normalize is not None:
            existing_data = normalize(existing_data)

        merged = self._merge_preserving_user(existing_data, shipped_data)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination_original == merged:
            return
        self._write_yaml_if_changed(destination, merged)

    def _prepare_text(self, destination: Path, shipped: Path, legacy: Path | None = None) -> None:
        """Create one persistent text template, preferring the previous user's copy when available."""
        if destination.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = legacy if legacy is not None and legacy.is_file() else shipped
        try:
            shutil.copy2(source, destination)
        except OSError:
            try:
                destination.write_text("", encoding="utf-8")
            except OSError:
                pass

    @staticmethod
    def _first_existing(*candidates: Path) -> Path | None:
        """Return the first existing migration candidate or None when no legacy file is available."""
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _copy_legacy_file_if_missing(source: Path, destination: Path) -> None:
        """Copy a non-YAML state file from the old data root only when the new destination does not exist."""
        if destination.exists() or not source.is_file():
            return
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError:
            pass

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        """Read YAML safely and return None for missing, unreadable, or invalid files."""
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None

    @classmethod
    def _merge_preserving_user(cls, user: Any, default: Any) -> Any:
        """Recursively add missing default schema while retaining every existing user scalar and list item."""
        if isinstance(user, dict) and isinstance(default, dict):
            result = deepcopy(user)
            for key, default_value in default.items():
                if key not in result:
                    result[key] = deepcopy(default_value)
                else:
                    result[key] = cls._merge_preserving_user(
                        result[key], default_value
                    )
            return result

        if isinstance(user, list) and isinstance(default, list):
            result = deepcopy(user)
            for item in default:
                if item not in result:
                    result.append(deepcopy(item))
            return result

        return deepcopy(user)

    @staticmethod
    def _normalize_settings(data: Any) -> Any:
        """Migrate known legacy settings keys and old shipped defaults without overriding explicit customization."""
        if not isinstance(data, dict):
            return data
        result = deepcopy(data)
        editor = result.get("editor")
        if isinstance(editor, dict):
            if "source_font_size" not in editor and "font_size" in editor:
                editor["source_font_size"] = editor.get("font_size")

        preview = result.get("preview")
        if isinstance(preview, dict):
            if preview.get("debounce_ms") == 220:
                preview["debounce_ms"] = 120
            if preview.get("large_document_debounce_ms") == 650:
                preview["large_document_debounce_ms"] = 420

            for key, old_name, new_name in (
                ("latex_template_path", "resources/latex_preview_template.tex", "templates/latex_preview_template.tex"),
                ("latex_beamer_template_path", "resources/latex_preview_beamer_template.tex", "templates/latex_preview_beamer_template.tex"),
            ):
                raw = str(preview.get(key, "")).strip()
                if raw in {"", old_name}:
                    preview[key] = new_name

        new_file = result.get("new_latex_file")
        if not isinstance(new_file, dict):
            result["new_latex_file"] = {}
        return result

    @staticmethod
    def _write_yaml_if_changed(path: Path, data: Any) -> None:
        """Atomically write YAML only when normalized content differs from the file already on disk."""
        text = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )
        try:
            old = path.read_text(encoding="utf-8")
        except OSError:
            old = None
        if old == text:
            return
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def migrate_legacy_ui_state(self, legacy_path: Path) -> None:
        """Import the older ~/.config UI-state JSON when no persistent Dropbox state exists yet."""
        if self.ui_state_path.exists() or not legacy_path.is_file():
            return
        try:
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.ui_state_path.parent.mkdir(parents=True, exist_ok=True)
                self.ui_state_path.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
        except (OSError, ValueError, json.JSONDecodeError):
            pass
