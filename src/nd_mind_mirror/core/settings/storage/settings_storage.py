from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import shutil
from typing import Any

import yaml


class SettingsStorage:
    """Own the persistent, user-editable Mind Mirror configuration files.

    Runtime settings live outside the replaceable application source tree so a
    new release cannot silently discard user choices.  Existing files are
    merged with new shipped defaults; user values win and only missing schema
    keys/default list entries are added.
    """

    DATA_ROOT = Path.home() / "Desktop" / "repo" / "data" / "nd_mind_mirror_project"

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.data_root = self.DATA_ROOT.expanduser()
        self.defaults_root = Path(__file__).resolve().parents[1] / "defaults"
        self.templates_dir = self.data_root / "templates"
        self.settings_path = self.data_root / "settings.yaml"
        self.shortcuts_path = self.data_root / "latex_shortcuts.yaml"
        self.ignore_path = self.data_root / "search_ignore.yaml"
        self.article_template_path = self.templates_dir / "latex_preview_template.tex"
        self.beamer_template_path = self.templates_dir / "latex_preview_beamer_template.tex"
        self.ui_state_path = self.data_root / "ui_state.json"
        self.session_path = self.data_root / "session.ini"

    def prepare(self) -> None:
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        self._prepare_yaml(
            destination=self.settings_path,
            shipped=self.defaults_root / "settings.yaml",
            legacy=self.project_root / "settings.yaml",
            normalize=self._normalize_settings,
        )
        self._prepare_yaml(
            destination=self.shortcuts_path,
            shipped=self.defaults_root / "latex_shortcuts.yaml",
            legacy=self.project_root / "latex_shortcuts.yaml",
        )
        self._prepare_yaml(
            destination=self.ignore_path,
            shipped=self.defaults_root / "search_ignore.yaml",
            legacy=self.project_root / "search_ignore.yaml",
        )
        self._prepare_text(
            self.article_template_path,
            self.defaults_root / "templates" / "latex_preview_template.tex",
        )
        self._prepare_text(
            self.beamer_template_path,
            self.defaults_root / "templates" / "latex_preview_beamer_template.tex",
        )

        # The JSON state file is intentionally created lazily by MainWindow.
        # An empty session.ini is harmless and makes the intended storage
        # location visible to the user immediately.
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
        shipped_data = self._read_yaml(shipped)
        if not isinstance(shipped_data, (dict, list)):
            shipped_data = {}

        existing_data = self._read_yaml(destination)
        if not isinstance(existing_data, (dict, list)):
            existing_data = None
        destination_original = deepcopy(existing_data)

        # On the first run after the storage move, start from the old file if
        # one exists. This preserves the values the user had in the project
        # directory before settings became external persistent data.
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

    def _prepare_text(self, destination: Path, shipped: Path) -> None:
        if destination.exists():
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(shipped, destination)
        except OSError:
            try:
                destination.write_text("", encoding="utf-8")
            except OSError:
                pass

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None

    @classmethod
    def _merge_preserving_user(cls, user: Any, default: Any) -> Any:
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

        # Scalar/type changes keep the user's value. New code is expected to
        # coerce or fall back safely when consuming it.
        return deepcopy(user)

    @staticmethod
    def _normalize_settings(data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        result = deepcopy(data)
        editor = result.get("editor")
        if isinstance(editor, dict):
            # v0.31 names the source-editor size explicitly. Migrate an older
            # customized font_size rather than introducing source_font_size=16
            # and accidentally hiding the user's real value.
            if "source_font_size" not in editor and "font_size" in editor:
                editor["source_font_size"] = editor.get("font_size")

        preview = result.get("preview")
        if isinstance(preview, dict):
            # Migrate only the exact old defaults; explicitly customized user
            # values remain untouched. These lower debounce values make the
            # live preview noticeably more responsive without restarting
            # LuaLaTeX on every keystroke.
            if preview.get("debounce_ms") == 220:
                preview["debounce_ms"] = 120
            if preview.get("large_document_debounce_ms") == 650:
                preview["large_document_debounce_ms"] = 420

            # Old relative template paths pointed into the application tree.
            # Persistent copies now live next to settings.yaml.
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
