"""Pinned/Open tab controller without explicit overflow-arrow widgets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from nd_mind_mirror.ui.switcher.hover_proxy_tab_bar import HoverProxyTabBar
from nd_mind_mirror.ui.window.main.pinned_tab_controller import PinnedTabController


class StablePinnedTabController(PinnedTabController):
    """Use proxy rows without extra explicit downward-triangle buttons."""

    def _make_row(self, label_text: str):
        container = QWidget(self._panel)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label = QLabel(label_text, container)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumWidth(44)
        layout.addWidget(label)

        bar = HoverProxyTabBar(container)
        bar.setDocumentMode(True)
        bar.setMovable(True)
        bar.setExpanding(False)
        bar.setUsesScrollButtons(False)
        bar.setChangeCurrentOnDrag(False)
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
