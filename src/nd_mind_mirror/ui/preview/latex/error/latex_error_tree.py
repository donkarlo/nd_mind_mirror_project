from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import QHeaderView, QStyle, QTreeWidget, QTreeWidgetItem

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)


class LatexErrorTree(QTreeWidget):
    """Readable, clickable tree for LaTeX failures and include chains."""

    source_location_requested = Signal(str, int, int)

    _PATH_ROLE = Qt.ItemDataRole.UserRole
    _LINE_ROLE = Qt.ItemDataRole.UserRole + 1
    _COLUMN_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(("Trace / problem", "Location / details"))
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(False)
        self.setWordWrap(True)
        self.setIndentation(22)
        self.setAnimated(True)
        self.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.itemDoubleClicked.connect(self._activate_item)
        self._apply_style()

    def show_diagnostic(self, diagnostic: LatexDiagnostic) -> None:
        self.clear()
        self._append_node(None, diagnostic.root)
        self.expandAll()
        self.scrollToTop()

    def _append_node(
        self,
        parent: QTreeWidgetItem | None,
        node: LatexDiagnosticNode,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem((node.title, node.detail))
        item.setIcon(0, self._icon_for(node.kind))
        self._apply_kind(item, node.kind)
        if node.source_path is not None:
            item.setData(0, self._PATH_ROLE, str(node.source_path))
            item.setData(0, self._LINE_ROLE, node.line)
            item.setData(0, self._COLUMN_ROLE, node.column)
            item.setToolTip(
                0,
                f"Double-click to open {node.source_path}:{node.line}:{node.column}",
            )
        if node.target_path is not None:
            item.setToolTip(1, str(node.target_path))

        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)

        for child in node.children:
            self._append_node(item, child)
        return item

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        path = item.data(0, self._PATH_ROLE)
        if not path:
            return
        line = int(item.data(0, self._LINE_ROLE) or 1)
        column = int(item.data(0, self._COLUMN_ROLE) or 1)
        self.source_location_requested.emit(str(path), line, column)

    def _icon_for(self, kind: str):
        style = self.style()
        if kind == "error" or kind == "missing":
            return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        if kind == "warning":
            return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        if kind == "file":
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        if kind == "workspace":
            return style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        if kind == "reference":
            return style.standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
        if kind == "compiler":
            return style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        return style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)

    def _apply_kind(self, item: QTreeWidgetItem, kind: str) -> None:
        if kind in {"error", "missing"}:
            brush = QBrush(QColor(196, 52, 52))
            item.setForeground(0, brush)
            item.setForeground(1, brush)
        elif kind == "warning":
            brush = QBrush(QColor(176, 112, 18))
            item.setForeground(0, brush)
            item.setForeground(1, brush)
        elif kind in {"workspace", "file"}:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

    def _apply_style(self) -> None:
        palette = self.palette()
        base = palette.color(QPalette.ColorRole.Base).name()
        alternate = palette.color(QPalette.ColorRole.AlternateBase).name()
        text = palette.color(QPalette.ColorRole.Text).name()
        border = palette.color(QPalette.ColorRole.Mid).name()
        highlight = palette.color(QPalette.ColorRole.Highlight).name()
        highlighted_text = palette.color(QPalette.ColorRole.HighlightedText).name()
        self.setStyleSheet(
            "QTreeWidget {"
            f"background: {base};"
            f"alternate-background-color: {alternate};"
            f"color: {text};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "padding: 4px;"
            "}"
            "QTreeWidget::item {"
            "min-height: 26px;"
            "padding: 3px 5px;"
            "border-radius: 4px;"
            "}"
            "QTreeWidget::item:selected {"
            f"background: {highlight};"
            f"color: {highlighted_text};"
            "}"
        )
