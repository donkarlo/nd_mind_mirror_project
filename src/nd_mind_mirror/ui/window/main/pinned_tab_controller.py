"""Keep pinned and ordinary editor tabs in two path-mapped, reorderable proxy rows."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QStyle,
    QStyleOptionTab,
    QStylePainter,
    QTabBar,
    QWidget,
)


class _SingleActiveProxyTabBar(QTabBar):
    """Paint selection only when this row owns the application's active file."""

    def __init__(self, parent=None) -> None:
        """Initialize a proxy tab row with selection painting enabled."""
        super().__init__(parent)
        self._selection_visible = True

    def set_selection_visible(self, visible: bool) -> None:
        """Show or suppress this row's selected-tab appearance without disabling clicks."""
        value = bool(visible)
        if value == self._selection_visible:
            return
        self._selection_visible = value
        self.update()

    def paintEvent(self, event) -> None:
        """Preserve the native tab style while suppressing selection in the inactive row."""
        if self._selection_visible:
            super().paintEvent(event)
            return

        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            option.state &= ~QStyle.StateFlag.State_Selected
            option.state &= ~QStyle.StateFlag.State_HasFocus
            painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)


class PinnedTabController:
    """Persist pins and visible tab order while mapping proxy rows to real editor pages."""

    _PIN_ORDER_KEY = "tabs/pinned_paths_json"
    _OPEN_ORDER_KEY = "tabs/open_order_paths_json"

    def __init__(self, editor_panel, session_settings, open_callback) -> None:
        """Install proxy tab rows and restore persisted pinned files and row order."""
        self._panel = editor_panel
        self._settings = session_settings
        self._open_callback = open_callback
        self._pinned_paths = self._load_path_list(self._PIN_ORDER_KEY)
        self._open_order_paths = self._load_path_list(self._OPEN_ORDER_KEY)
        self._syncing_rows = False
        self._pin_bar_paths: list[str] = []
        self._open_bar_paths: list[str] = []

        self._original_open_file = editor_panel.open_file
        self._original_close_tab = editor_panel.close_tab
        self._original_refresh_titles = editor_panel._refresh_tab_titles

        self._install_proxy_rows()
        self._install_wrappers()
        self._install_context_menus()
        self._panel._tabs.currentChanged.connect(self._on_real_current_changed)
        QTimer.singleShot(0, self.restore_pinned_files)

    def pin_path(self, path: str | Path) -> None:
        """Open a file if needed and move its visible alias to the pinned row."""
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file():
            return
        canonical = str(candidate)
        if canonical not in self._pinned_paths:
            self._pinned_paths.append(canonical)
        self._open_order_paths = [value for value in self._open_order_paths if value != canonical]
        if self._panel._index_for_path(candidate) < 0:
            self._open_callback(candidate)
        self._save_orders()
        self._panel._refresh_tab_titles()

    def unpin_path(self, path: str | Path) -> None:
        """Move a pinned file alias back to the ordinary open-file row."""
        candidate = str(Path(path).expanduser().resolve())
        self._pinned_paths = [value for value in self._pinned_paths if value != candidate]
        if self._panel._index_for_path(Path(candidate)) >= 0 and candidate not in self._open_order_paths:
            self._open_order_paths.append(candidate)
        self._save_orders()
        self._panel._refresh_tab_titles()

    def rename_path(self, old_path: str, new_path: str) -> None:
        """Rewrite persisted pin and open-row paths after file or folder rename."""
        old_root = Path(old_path).expanduser().resolve()
        new_root = Path(new_path).expanduser().resolve()
        pins, pins_changed = self._rewrite_order_paths(self._pinned_paths, old_root, new_root)
        opens, opens_changed = self._rewrite_order_paths(self._open_order_paths, old_root, new_root)
        if pins_changed or opens_changed:
            self._pinned_paths = pins
            self._open_order_paths = opens
            self._save_orders()
            self._panel._refresh_tab_titles()

    def remove_deleted_path(self, deleted_path: str) -> None:
        """Forget persisted tab entries that point at a deleted path or its children."""
        root = Path(deleted_path).expanduser().resolve()
        pins = self._without_path_tree(self._pinned_paths, root)
        opens = self._without_path_tree(self._open_order_paths, root)
        if pins != self._pinned_paths or opens != self._open_order_paths:
            self._pinned_paths = pins
            self._open_order_paths = opens
            self._save_orders()
            self._panel._refresh_tab_titles()

    def restore_pinned_files(self) -> None:
        """Reopen persisted pins and rebuild both path-mapped tab rows."""
        valid: list[str] = []
        for raw in self._pinned_paths:
            path = Path(raw)
            if not path.is_file():
                continue
            canonical = str(path.resolve())
            if canonical not in valid:
                valid.append(canonical)
            if self._panel._index_for_path(path) < 0:
                self._open_callback(path)
        self._pinned_paths = valid
        self._save_orders()
        self._panel._refresh_tab_titles()

    def _install_proxy_rows(self) -> None:
        """Hide the real tab bar and insert reorderable Pinned and Open proxy rows."""
        self._pin_row, self._pin_bar = self._make_row("Pinned")
        self._open_row, self._open_bar = self._make_row("Open")
        self._open_bar.setTabsClosable(True)
        self._open_bar.tabCloseRequested.connect(self._on_open_close_requested)

        self._pin_bar.tabBarClicked.connect(self._on_pin_bar_clicked)
        self._open_bar.tabBarClicked.connect(self._on_open_bar_clicked)
        self._pin_bar.tabMoved.connect(self._on_pin_tab_moved)
        self._open_bar.tabMoved.connect(self._on_open_tab_moved)

        real_bar = self._panel._tabs.tabBar()
        real_bar.hide()
        real_bar.setMaximumHeight(0)

        index = self._panel.panel_layout.indexOf(self._panel._tabs)
        insert_at = max(index, 0)
        self._panel.panel_layout.insertWidget(insert_at, self._pin_row)
        self._panel.panel_layout.insertWidget(insert_at + 1, self._open_row)

    def _make_row(self, label_text: str) -> tuple[QWidget, QTabBar]:
        """Create one fixed-width draggable proxy tab row using the panel's tab sizing."""
        container = QWidget(self._panel)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(label_text, container)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumWidth(44)
        layout.addWidget(label)

        bar = _SingleActiveProxyTabBar(container)
        bar.setDocumentMode(True)
        bar.setMovable(True)
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.TextElideMode.ElideNone)
        bar.setMinimumHeight(28)
        tab_width = int(getattr(self._panel, "_TAB_WIDTH", 220))
        bar.setStyleSheet(
            "QTabBar::tab {"
            f"min-width: {tab_width}px;"
            f"max-width: {tab_width}px;"
            "}"
        )
        layout.addWidget(bar, 1)
        return container, bar

    def _install_wrappers(self) -> None:
        """Wrap editor lifecycle hooks so proxy rows stay synchronized."""
        self._panel.open_file = self._open_file
        self._panel.close_tab = self._close_tab
        self._panel._least_recently_used_unmodified_index = (
            self._least_recently_used_unmodified_index
        )
        self._panel._refresh_tab_titles = self._refresh_tab_titles

    def _install_context_menus(self) -> None:
        """Add Pin and Unpin menus to the two visible proxy rows."""
        self._open_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._open_bar.customContextMenuRequested.connect(self._show_open_context_menu)

        self._pin_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._pin_bar.customContextMenuRequested.connect(self._show_pinned_context_menu)

    def _show_open_context_menu(self, position) -> None:
        """Offer Pin for the ordinary proxy tab under the pointer."""
        index = self._open_bar.tabAt(position)
        if index < 0 or index >= len(self._open_bar_paths):
            return
        path = self._open_bar_paths[index]
        menu = QMenu(self._open_bar)
        action = menu.addAction("Pin Tab")
        action.triggered.connect(lambda: self.pin_path(path))
        menu.exec(self._open_bar.mapToGlobal(position))

    def _show_pinned_context_menu(self, position) -> None:
        """Offer Unpin for the pinned proxy tab under the pointer."""
        index = self._pin_bar.tabAt(position)
        if index < 0 or index >= len(self._pin_bar_paths):
            return
        path = self._pin_bar_paths[index]
        menu = QMenu(self._pin_bar)
        action = menu.addAction("Unpin Tab")
        action.triggered.connect(lambda: self.unpin_path(path))
        menu.exec(self._pin_bar.mapToGlobal(position))

    def _open_file(self, path, content, select=True) -> bool:
        """Delegate file opening, remember ordinary-row order, then synchronize aliases."""
        opened = self._original_open_file(path, content, select)
        if opened:
            canonical = str(Path(path).expanduser().resolve())
            if canonical not in self._pinned_paths and canonical not in self._open_order_paths:
                self._open_order_paths.append(canonical)
                self._save_orders()
            QTimer.singleShot(0, self._panel._refresh_tab_titles)
        return opened

    def _close_tab(self, index: int) -> None:
        """Protect pinned files and remove closed ordinary files from persisted order."""
        path = self._panel.path_at(index)
        if path is not None and self._is_pinned(path) and Path(path).exists():
            return
        if path is not None and self._is_pinned(path):
            self.unpin_path(path)
        canonical = (
            str(Path(path).expanduser().resolve()) if path is not None else None
        )
        self._original_close_tab(index)
        if canonical is not None:
            updated = [value for value in self._open_order_paths if value != canonical]
            if updated != self._open_order_paths:
                self._open_order_paths = updated
                self._save_orders()
        QTimer.singleShot(0, self._panel._refresh_tab_titles)

    def _least_recently_used_unmodified_index(self) -> int:
        """Return the oldest unmodified ordinary real page for automatic eviction."""
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
        """Refresh real titles and rebuild both visible rows from canonical paths."""
        self._original_refresh_titles()
        self._sync_rows()

    def _on_real_current_changed(self, _index: int) -> None:
        """Mirror programmatic real-page changes into exactly one active proxy row."""
        if not self._syncing_rows:
            self._sync_rows()

    def _sync_rows(self) -> None:
        """Rebuild both proxy rows while preserving their separately persisted orders."""
        if self._syncing_rows:
            return
        self._syncing_rows = True
        try:
            tabs = self._panel._tabs
            current_path = self._panel.current_path()
            canonical_current = (
                str(Path(current_path).expanduser().resolve())
                if current_path is not None
                else None
            )

            self._pin_bar.blockSignals(True)
            self._open_bar.blockSignals(True)
            try:
                self._clear_bar(self._pin_bar)
                self._clear_bar(self._open_bar)
                self._pin_bar_paths = []
                self._open_bar_paths = []

                open_by_path: dict[str, tuple[int, str]] = {}
                real_open_order: list[str] = []
                for real_index in range(tabs.count()):
                    path = self._panel.path_at(real_index)
                    if path is None:
                        continue
                    canonical = str(Path(path).expanduser().resolve())
                    title = tabs.tabText(real_index)
                    if title.startswith("[P] "):
                        title = title[4:]
                    open_by_path[canonical] = (real_index, title)
                    real_open_order.append(canonical)

                for raw in self._pinned_paths:
                    canonical = str(Path(raw).expanduser().resolve())
                    item = open_by_path.get(canonical)
                    if item is None:
                        continue
                    _real_index, title = item
                    proxy_index = self._pin_bar.addTab(title)
                    self._pin_bar.setTabToolTip(proxy_index, canonical)
                    self._pin_bar_paths.append(canonical)

                ordinary_paths = [
                    path for path in real_open_order if path not in self._pinned_paths
                ]
                ordered_ordinary = [
                    path for path in self._open_order_paths if path in ordinary_paths
                ]
                ordered_ordinary.extend(
                    path for path in ordinary_paths if path not in ordered_ordinary
                )
                if ordered_ordinary != self._open_order_paths:
                    self._open_order_paths = list(ordered_ordinary)
                    self._save_orders()

                for canonical in ordered_ordinary:
                    _real_index, title = open_by_path[canonical]
                    proxy_index = self._open_bar.addTab(title)
                    self._open_bar.setTabToolTip(proxy_index, canonical)
                    self._open_bar_paths.append(canonical)

                pin_index = self._index_of_path(self._pin_bar_paths, canonical_current)
                open_index = self._index_of_path(self._open_bar_paths, canonical_current)
                self._pin_bar.setCurrentIndex(pin_index)
                self._open_bar.setCurrentIndex(open_index)
                self._pin_bar.set_selection_visible(pin_index >= 0)
                self._open_bar.set_selection_visible(open_index >= 0)
            finally:
                self._pin_bar.blockSignals(False)
                self._open_bar.blockSignals(False)
        finally:
            self._syncing_rows = False

    @staticmethod
    def _clear_bar(bar: QTabBar) -> None:
        """Remove all proxy tabs without touching real editor pages."""
        while bar.count() > 0:
            bar.removeTab(0)

    @staticmethod
    def _index_of_path(paths: list[str], path: str | None) -> int:
        """Return a proxy-row index or -1 when that row does not own the path."""
        if path is None:
            return -1
        try:
            return paths.index(path)
        except ValueError:
            return -1

    def _on_pin_bar_clicked(self, index: int) -> None:
        """Activate the real page represented by a clicked pinned proxy tab."""
        if 0 <= index < len(self._pin_bar_paths):
            self._activate_path(self._pin_bar_paths[index])

    def _on_open_bar_clicked(self, index: int) -> None:
        """Activate the real page represented by a clicked ordinary proxy tab."""
        if 0 <= index < len(self._open_bar_paths):
            self._activate_path(self._open_bar_paths[index])

    def _on_pin_tab_moved(self, from_index: int, to_index: int) -> None:
        """Persist the pinned-row order immediately after a drag operation."""
        if self._syncing_rows or from_index == to_index:
            return
        if not (0 <= from_index < len(self._pin_bar_paths)):
            return
        item = self._pin_bar_paths.pop(from_index)
        destination = max(0, min(to_index, len(self._pin_bar_paths)))
        self._pin_bar_paths.insert(destination, item)
        self._pinned_paths = list(self._pin_bar_paths)
        self._save_orders()

    def _on_open_tab_moved(self, from_index: int, to_index: int) -> None:
        """Persist the ordinary open-row order immediately after a drag operation."""
        if self._syncing_rows or from_index == to_index:
            return
        if not (0 <= from_index < len(self._open_bar_paths)):
            return
        item = self._open_bar_paths.pop(from_index)
        destination = max(0, min(to_index, len(self._open_bar_paths)))
        self._open_bar_paths.insert(destination, item)
        self._open_order_paths = list(self._open_bar_paths)
        self._save_orders()

    def _activate_path(self, raw_path: str) -> None:
        """Select one real editor page by canonical path and reveal that path in Navigator."""
        path = Path(raw_path).expanduser().resolve()
        target = self._panel._index_for_path(path)
        if target < 0:
            return
        self._panel._tabs.setCurrentIndex(target)
        editor = self._panel._tabs.widget(target)
        if editor is not None:
            editor.setFocus()
        self._panel.active_tab_clicked.emit(str(path))
        self._sync_rows()

    def _on_open_close_requested(self, index: int) -> None:
        """Forward an ordinary proxy close button to the real tab close workflow."""
        if index < 0 or index >= len(self._open_bar_paths):
            return
        target = self._panel._index_for_path(Path(self._open_bar_paths[index]))
        if target < 0:
            return
        handler = getattr(self._panel, "_on_tab_close_requested", None)
        if callable(handler):
            handler(target)
        else:
            self._panel.close_tab(target)

    def _is_pinned(self, path: str | Path) -> bool:
        """Return whether a canonical path is in the persisted pinned set."""
        return str(Path(path).expanduser().resolve()) in self._pinned_paths

    def _load_path_list(self, key: str) -> list[str]:
        """Load one unique canonical-path order list from session settings."""
        raw = str(self._settings.value(key, "[]") or "[]")
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

    @staticmethod
    def _rewrite_order_paths(
        values: list[str], old_root: Path, new_root: Path
    ) -> tuple[list[str], bool]:
        """Rewrite path-list entries below one renamed filesystem root."""
        changed = False
        updated: list[str] = []
        for raw in values:
            candidate = Path(raw)
            try:
                relative = candidate.relative_to(old_root)
            except ValueError:
                rewritten = raw
            else:
                rewritten = str((new_root / relative).resolve())
                changed = True
            if rewritten not in updated:
                updated.append(rewritten)
        return updated, changed

    @staticmethod
    def _without_path_tree(values: list[str], root: Path) -> list[str]:
        """Return list entries that are not the deleted path or one of its descendants."""
        kept: list[str] = []
        for raw in values:
            candidate = Path(raw)
            try:
                candidate.relative_to(root)
            except ValueError:
                kept.append(raw)
        return kept

    def _save_orders(self) -> None:
        """Persist pinned and ordinary-row orders as compact JSON immediately."""
        self._settings.setValue(
            self._PIN_ORDER_KEY,
            json.dumps(self._pinned_paths, ensure_ascii=False, separators=(",", ":")),
        )
        self._settings.setValue(
            self._OPEN_ORDER_KEY,
            json.dumps(
                self._open_order_paths,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        self._settings.sync()
