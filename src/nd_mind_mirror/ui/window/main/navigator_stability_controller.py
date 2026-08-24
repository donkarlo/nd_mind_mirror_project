"""Keep Navigator viewport stable across repeated reveals and proxy-model relayouts."""

from __future__ import annotations

from pathlib import Path
from types import MethodType

from PySide6.QtCore import QItemSelectionModel, QTimer
from PySide6.QtWidgets import QAbstractItemView


class NavigatorStabilityController:
    """Suppress tiny Navigator jumps without changing file-operation semantics."""

    def __init__(self, main_window) -> None:
        self._window = main_window
        self._panel = main_window._file_system_panel
        self._tree = self._panel._tree
        self._base_select_path = self._panel.select_path
        self._saved_vertical_scroll = None
        self._saved_horizontal_scroll = None
        self._layout_restore_generation = 0

        self._tree.setUniformRowHeights(True)
        self._tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._install_non_jumping_select_path()
        self._install_layout_scroll_guard()
        self._install_move_scroll_guard()

    def _install_non_jumping_select_path(self) -> None:
        """Avoid scrollTo when the requested path is already visible in the viewport."""
        controller = self

        def select_path(panel, path: str | Path, *, force_reveal: bool = False) -> None:
            target = Path(path).expanduser().resolve()
            if not panel._is_same_or_child(target, panel._root_path):
                return

            index = panel._view_index_for_path(target)
            if index.isValid() and controller._index_is_visible(index):
                current = panel.selected_path()
                same_current = False
                if current:
                    try:
                        same_current = Path(current).expanduser().resolve() == target
                    except OSError:
                        same_current = False

                if same_current:
                    panel._pending_reveal = None
                    return

                selection_model = controller._tree.selectionModel()
                if selection_model is not None:
                    flags = (
                        QItemSelectionModel.SelectionFlag.ClearAndSelect
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
                    selection_model.select(index, flags)
                controller._tree.setCurrentIndex(index)
                panel._pending_reveal = None
                return

            controller._base_select_path(target, force_reveal=force_reveal)

        self._panel.select_path = MethodType(select_path, self._panel)

    def _index_is_visible(self, index) -> bool:
        """Return whether an index already occupies visible viewport pixels."""
        if not index.isValid():
            return False
        rect = self._tree.visualRect(index)
        if not rect.isValid() or rect.height() <= 0:
            return False
        return self._tree.viewport().rect().intersects(rect)

    def _install_layout_scroll_guard(self) -> None:
        """Preserve pixel scroll offsets when the proxy emits a harmless relayout."""
        model = self._tree.model()
        if model is None:
            return
        try:
            model.layoutAboutToBeChanged.connect(self._capture_layout_scroll)
            model.layoutChanged.connect(self._restore_layout_scroll)
        except (AttributeError, RuntimeError, TypeError):
            return

    def _capture_layout_scroll(self, *_args) -> None:
        self._layout_restore_generation += 1
        self._saved_vertical_scroll = self._tree.verticalScrollBar().value()
        self._saved_horizontal_scroll = self._tree.horizontalScrollBar().value()

    def _restore_layout_scroll(self, *_args) -> None:
        generation = self._layout_restore_generation
        vertical = self._saved_vertical_scroll
        horizontal = self._saved_horizontal_scroll
        if vertical is None or horizontal is None:
            return
        QTimer.singleShot(
            0,
            lambda token=generation, y=vertical, x=horizontal:
            self._apply_saved_scroll(token, y, x),
        )

    def _apply_saved_scroll(self, generation: int, vertical: int, horizontal: int) -> None:
        if generation != self._layout_restore_generation:
            return
        self._tree.verticalScrollBar().setValue(vertical)
        self._tree.horizontalScrollBar().setValue(horizontal)

    def _install_move_scroll_guard(self) -> None:
        """Keep the viewport fixed while a rename or drag/move changes model indexes."""
        self._panel.path_about_to_move.connect(self._capture_move_scroll)
        self._panel.path_renamed.connect(self._restore_move_scroll)

    def _capture_move_scroll(self, *_args) -> None:
        self._saved_vertical_scroll = self._tree.verticalScrollBar().value()
        self._saved_horizontal_scroll = self._tree.horizontalScrollBar().value()

    def _restore_move_scroll(self, *_args) -> None:
        vertical = self._saved_vertical_scroll
        horizontal = self._saved_horizontal_scroll
        if vertical is None or horizontal is None:
            return
        for delay in (0, 25, 70):
            QTimer.singleShot(
                delay,
                lambda y=vertical, x=horizontal: (
                    self._tree.verticalScrollBar().setValue(y),
                    self._tree.horizontalScrollBar().setValue(x),
                ),
            )
