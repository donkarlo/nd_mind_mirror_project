"""Regression tests for configurable PDF Preview Copy and Find shortcuts."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import yaml

from nd_mind_mirror.ui.window.main.shortcut_settings_dialog import ShortcutSettingsDialog
from nd_mind_mirror.ui.window.main.shortcut_store import ShortcutStore


DEFAULTS = (
    Path(__file__).resolve().parents[1]
    / "src/nd_mind_mirror/core/settings/defaults/keyboard_shortcuts.yaml"
)


def test_default_shortcuts_describe_pinned_preview_and_preserve_old_user_keys(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "keyboard_shortcuts.yaml").write_text(
        yaml.safe_dump({"shortcuts": {
            "find.current": {"label": "Find in current tab", "keys": "Ctrl+J"},
            "editor.bold": {"label": "My own editor action", "keys": "Ctrl+B"},
        }}),
        encoding="utf-8",
    )
    store = ShortcutStore(data, DEFAULTS)
    entries = store.entries()
    assert entries["find.current"]["keys"] == "Ctrl+J"
    assert "Source, Visual" in entries["find.current"]["label"]
    assert entries["editor.bold"]["label"] == "My own editor action"
    assert entries["preview.find"]["keys"] == "Ctrl+F"
    assert "pinned" in entries["preview.find"]["label"].lower()
    assert entries["preview.copy"]["keys"] == "Ctrl+C"
    assert "selected" in entries["preview.copy"]["label"].lower()


def test_shortcut_dialog_allows_find_in_separate_window_scopes(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = ShortcutStore(tmp_path, DEFAULTS)
    applied = []
    dialog = ShortcutSettingsDialog(store, lambda: applied.append(True))
    try:
        rows = {
            dialog._table.item(row, 0).data(Qt.ItemDataRole.UserRole): row
            for row in range(dialog._table.rowCount())
        }
        assert "preview.find" in rows and "preview.copy" in rows
        assert "pinned" in dialog._table.item(rows["preview.find"], 0).text().lower()
        dialog.apply()
        assert applied == [True]
        assert store.entries()["find.current"]["keys"] == "Ctrl+F"
        assert store.entries()["preview.find"]["keys"] == "Ctrl+F"
        assert store.entries()["preview.copy"]["keys"] == "Ctrl+C"

        dialog._table.item(rows["preview.find"], 1).setText("Ctrl+Shift+G")
        dialog._table.item(rows["preview.copy"], 1).setText("Ctrl+Shift+C")
        dialog.apply()
        assert applied == [True, True]
        assert store.entries()["preview.find"]["keys"] == "Ctrl+Shift+G"
        assert store.entries()["preview.copy"]["keys"] == "Ctrl+Shift+C"
    finally:
        dialog.close()
        app.processEvents()
