"""Keep explicitly pinned editor tabs open, persistent, and ordered before ordinary tabs."""

import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMenu


class PinnedTabController:
    """Persist pinned paths, protect them from automatic closure, and keep them at the front of the tab bar."""

    def __init__(self, editor_panel, session_settings, open_callback) -> None:
        """Install tab wrappers/context menu and restore pinned paths from the previous session."""
        self._panel = editor_panel
        self._settings = session_settings
        self._open_callback = open_callback
        self._reordering = False
        self._pinned_paths = self._load_paths()
        self._original_open_file = editor_panel.open_file
        self._original_close_tab = editor_panel.close_tab
        self._original_refresh_titles = editor_panel._refresh_tab_titles
        self._install_wrappers()
        self._install_context_menu()
        QTimer.singleShot(0, self.restore_pinned_files)

    def pin_path(self, path: str | Path) -> None:
        """Open and pin a file path, then move its tab into the leading pinned group."""
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file():
            return
        if str(candidate) not in self._pinned_paths:
            self._pinned_paths.append(str(candidate))
        if self._panel._index_for_path(candidate) < 0:
            self._open_callback(candidate)
        self._save_paths()
        self._reorder_pinned()
        self._panel._refresh_tab_titles()

    def unpin_path(self, path: str | Path) -> None:
        """Remove one file from the persistent pinned set while leaving its tab open."""
        candidate = str(Path(path).expanduser().resolve())
        self._pinned_paths = [value for value in self._pinned_paths if value != candidate]
        self._save_paths()
        self._panel._refresh_tab_titles()

    def rename_path(self, old_path: str, new_path: str) -> None:
        """Rewrite pinned paths when a pinned file or parent directory is moved or renamed."""
        old_root = Path(old_path).expanduser().resolve()
        new_root = Path(new_path).expanduser().resolve()
        changed = False
        updated: list[str] = []
        for raw in self._pinned_paths:
            candidate = Path(raw)
            try:
                relative = candidate.relative_to(old_root)
            except ValueError:
                updated.append(raw)
                continue
            updated.append(str((new_root / relative).resolve()))
            changed = True
        if changed:
            self._pinned_paths = updated
            self._save_paths()
            self._panel._refresh_tab_titles()

    def remove_deleted_path(self, deleted_path: str) -> None:
        """Forget pins that point at a deleted file or anything below a deleted directory."""
        root = Path(deleted_path).expanduser().resolve()
        kept: list[str] = []
        for raw in self._pinned_paths:
            candidate = Path(raw)
            try:
                candidate.relative_to(root)
            except ValueError:
                kept.append(raw)
        if kept != self._pinned_paths:
            self._pinned_paths = kept
            self._save_paths()
            self._panel._refresh_tab_titles()

    def restore_pinned_files(self) -> None:
        """Reopen existing pinned files that were not already restored by the normal session loader."""
        valid: list[str] = []
        for raw in self._pinned_paths:
            path = Path(raw)
            if path.is_file():
                valid.append(str(path.resolve()))
                if self._panel._index_for_path(path) < 0:
                    self._open_callback(path)
        self._pinned_paths = valid
        self._save_paths()
        self._reorder_pinned()
        self._panel._refresh_tab_titles()

    def _install_wrappers(self) -> None:
        """Wrap EditorPanel tab lifecycle methods without replacing the large existing panel implementation."""
        self._panel.open_file = self._open_file
        self._panel.close_tab = self._close_tab
        self._panel._least_recently_used_unmodified_index = self._least_recently_used_unmodified_index
        self._panel._refresh_tab_titles = self._refresh_tab_titles

    def _install_context_menu(self) -> None:
        """Add Pin/Unpin to the tab bar's right-click menu."""
        bar = self._panel._tabs.tabBar()
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._show_context_menu)
        bar.tabMoved.connect(lambda _from, _to: QTimer.singleShot(0, self._reorder_pinned))

    def _show_context_menu(self, position) -> None:
        """Show Pin or Unpin for the tab under the pointer."""
        bar = self._panel._tabs.tabBar()
        index = bar.tabAt(position)
        if index < 0:
            return
        path = self._panel.path_at(index)
        if path is None:
            return
        menu = QMenu(bar)
        if self._is_pinned(path):
            action = menu.addAction("Unpin Tab")
            action.triggered.connect(lambda: self.unpin_path(path))
        else:
            action = menu.addAction("Pin Tab")
            action.triggered.connect(lambda: self.pin_path(path))
        menu.exec(bar.mapToGlobal(position))

    def _open_file(self, path, content, select=True) -> bool:
        """Delegate file opening, then restore pinned ordering and decoration."""
        opened = self._original_open_file(path, content, select)
        if opened:
            QTimer.singleShot(0, self._reorder_pinned)
            QTimer.singleShot(0, self._panel._refresh_tab_titles)
        return opened

    def _close_tab(self, index: int) -> None:
        """Prevent ordinary close requests from closing an existing pinned file."""
        path = self._panel.path_at(index)
        if path is not None and self._is_pinned(path) and Path(path).exists():
            return
        if path is not None and self._is_pinned(path):
            self.unpin_path(path)
        self._original_close_tab(index)

    def _least_recently_used_unmodified_index(self) -> int:
        """Return the least-recent unmodified non-pinned tab for automatic capacity eviction."""
        candidates: list[tuple[int, int]] = []
        for index in range(self._panel._tabs.count()):
            editor = self._panel._tabs.widget(index)
            path = self._panel.path_at(index)
            if path is not None and self._is_pinned(path):
                continue
            document = editor.document() if hasattr(editor, "document") else None
            if document is not None and document.isModified():
                continue
            candidates.append((int(self._panel._last_activated.get(editor, 0)), index))
        return min(candidates)[1] if candidates else -1

    def _refresh_tab_titles(self) -> None:
        """Run the original title refresher and prefix pinned tabs with a compact textual marker."""
        self._original_refresh_titles()
        bar = self._panel._tabs.tabBar()
        for index in range(self._panel._tabs.count()):
            path = self._panel.path_at(index)
            title = bar.tabText(index)
            if title.startswith("[P] "):
                title = title[4:]
            if path is not None and self._is_pinned(path):
                title = "[P] " + title
                bar.setTabToolTip(index, f"Pinned — {path}")
            elif path is not None:
                bar.setTabToolTip(index, str(path))
            bar.setTabText(index, title)

    def _reorder_pinned(self) -> None:
        """Move currently open pinned tabs to leading indices while preserving saved pin order."""
        if self._reordering:
            return
        self._reordering = True
        try:
            bar = self._panel._tabs.tabBar()
            target_index = 0
            for raw in self._pinned_paths:
                current = self._panel._index_for_path(Path(raw))
                if current >= 0 and current != target_index:
                    bar.moveTab(current, target_index)
                if current >= 0:
                    target_index += 1
        finally:
            self._reordering = False

    def _is_pinned(self, path: str | Path) -> bool:
        """Return whether the canonical path is currently in the persistent pinned list."""
        return str(Path(path).expanduser().resolve()) in self._pinned_paths

    def _load_paths(self) -> list[str]:
        """Load unique pinned paths from QSettings in their saved ordering."""
        raw = str(self._settings.value("tabs/pinned_paths_json", "[]") or "[]")
        try:
            values = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            values = []
        result: list[str] = []
        for value in values if isinstance(values, list) else []:
            candidate = str(Path(str(value)).expanduser())
            if candidate not in result:
                result.append(candidate)
        return result

    def _save_paths(self) -> None:
        """Persist pinned paths as compact JSON in the existing session settings file."""
        self._settings.setValue(
            "tabs/pinned_paths_json",
            json.dumps(self._pinned_paths, ensure_ascii=False, separators=(",", ":")),
        )
        self._settings.sync()
