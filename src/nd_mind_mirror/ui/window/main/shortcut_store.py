"""Persist configurable application keyboard shortcuts in a dedicated YAML file."""

from pathlib import Path
from typing import Any

from PySide6.QtGui import QKeySequence
import yaml

from nd_mind_mirror.ui.window.main.undo_redo_controller import UndoRedoController


class ShortcutStore:
    """Merge shipped shortcut defaults with the user's dedicated keyboard_shortcuts.yaml file."""

    def __init__(self, data_root: str | Path, default_path: str | Path) -> None:
        """Prepare the persistent shortcut file and install layout-safe editor undo/redo handling."""
        self.path = Path(data_root).expanduser().resolve() / "keyboard_shortcuts.yaml"
        self.default_path = Path(default_path).expanduser().resolve()
        self._entries = self._load_defaults()
        self._prepare_user_file()
        self._undo_redo_controller = UndoRedoController()

    def entries(self) -> dict[str, dict[str, str]]:
        """Return a defensive copy of action labels and key sequences keyed by stable action id."""
        return {key: dict(value) for key, value in self._entries.items()}

    def apply(self, bindings: dict[str, object]) -> None:
        """Apply configured key sequences to QAction and QShortcut targets through their native setter."""
        for action_id, target in bindings.items():
            entry = self._entries.get(action_id, {})
            keys = str(entry.get("keys", "")).strip()
            if target is None:
                continue
            sequence = QKeySequence(keys)
            if hasattr(target, "setShortcut"):
                target.setShortcut(sequence)
            elif hasattr(target, "setKey"):
                target.setKey(sequence)

    def save_keys(self, keys_by_id: dict[str, str]) -> None:
        """Persist edited key sequences atomically while retaining labels and unknown future entries."""
        for action_id, keys in keys_by_id.items():
            if action_id in self._entries:
                self._entries[action_id]["keys"] = str(keys).strip()
        self._write()

    def reload(self) -> None:
        """Reload the user's shortcut file and merge any missing shipped defaults."""
        self._prepare_user_file()

    def _load_defaults(self) -> dict[str, dict[str, str]]:
        """Load and normalize the bundled shortcut schema."""
        data = self._read_yaml(self.default_path)
        return self._normalize_entries(data)

    def _prepare_user_file(self) -> None:
        """Create or merge the user shortcut file so upgrades add only missing action ids."""
        user = self._normalize_entries(self._read_yaml(self.path))
        merged = {key: dict(value) for key, value in self._load_defaults().items()}
        for key, value in user.items():
            if key in merged:
                merged[key].update(value)
            else:
                merged[key] = dict(value)
        self._entries = merged
        self._write()

    def _write(self) -> None:
        """Write the current shortcut schema through a temporary file to avoid partial YAML updates."""
        payload: dict[str, Any] = {"shortcuts": self._entries}
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=100)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _read_yaml(path: Path) -> Any:
        """Return parsed YAML data or an empty mapping when the file is absent or invalid."""
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}

    @staticmethod
    def _normalize_entries(data: Any) -> dict[str, dict[str, str]]:
        """Normalize the shortcuts mapping into stable label/keys string dictionaries."""
        if not isinstance(data, dict):
            return {}
        raw = data.get("shortcuts", data)
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, str]] = {}
        for action_id, value in raw.items():
            if isinstance(value, dict):
                result[str(action_id)] = {
                    "label": str(value.get("label", action_id)),
                    "keys": str(value.get("keys", "")),
                }
            else:
                result[str(action_id)] = {"label": str(action_id), "keys": str(value)}
        return result
