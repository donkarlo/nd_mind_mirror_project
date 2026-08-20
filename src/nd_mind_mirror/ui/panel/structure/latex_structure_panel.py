from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
)

from nd_mind_mirror.core.latex.structure.latex_structure_parser import (
    LatexStructureParser,
)
from nd_mind_mirror.core.yaml.structure.yaml_structure_parser import (
    YamlStructureParser,
)
from nd_mind_mirror.ui.panel.base.panel import Panel


class LatexStructurePanel(Panel):
    line_activated = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__("Structure", parent)

        self._latex_parser = LatexStructureParser()
        self._yaml_parser = YamlStructureParser()
        self._path: Path | None = None
        self._source = ""
        self._indent_width = 10

        self.setMinimumWidth(90)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel("Structure", self)
        self._tree = QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(self._indent_width)
        self._tree.setAnimated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._tree.itemClicked.connect(
            self._on_item_clicked
        )

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self._rebuild)

        self.panel_layout.addWidget(self._label)
        self.panel_layout.addWidget(self._tree, 1)

    def apply_settings(
        self,
        indent_width: int,
        row_height: int = 24,
        tab_size: int = 4,
    ) -> None:
        self._indent_width = max(int(indent_width), 1)
        self._yaml_parser.set_tab_size(tab_size)
        self._tree.setIndentation(self._indent_width)
        self._tree.setStyleSheet(
            f"QTreeWidget::item {{ min-height: {max(int(row_height), 18)}px; }}"
        )

    def set_document(
        self,
        path: str | Path,
        source: str,
        immediate: bool = False,
    ) -> None:
        file_path = Path(path).expanduser().resolve()
        path_changed = file_path != self._path
        self._path = file_path
        self._source = source

        if file_path.suffix.lower() not in {".tex", ".yaml", ".yml"}:
            self.clear()
            return

        self._label.setText(f"Structure — {file_path.name}")
        if immediate or path_changed:
            self._refresh_timer.stop()
            self._rebuild()
        else:
            self._refresh_timer.start()

    def clear(self) -> None:
        self._refresh_timer.stop()
        self._path = None
        self._source = ""
        self._label.setText("Structure")
        self._tree.clear()

    def _rebuild(self) -> None:
        if (
            self._path is None
            or self._path.suffix.lower() not in {".tex", ".yaml", ".yml"}
        ):
            self.clear()
            return

        suffix = self._path.suffix.lower()
        structure = (
            self._latex_parser.parse(self._source)
            if suffix == ".tex"
            else self._yaml_parser.parse(self._source)
        )
        self._tree.setUpdatesEnabled(False)
        try:
            self._tree.clear()
            stack: list[tuple[int, QTreeWidgetItem]] = []

            for node in structure:
                while stack and stack[-1][0] >= node.level:
                    stack.pop()

                item = QTreeWidgetItem(
                    [f"{node.kind} — {node.title}"]
                )
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    node.line_number,
                )
                item.setToolTip(
                    0,
                    f"Line {node.line_number}: {node.kind}",
                )

                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self._tree.addTopLevelItem(item)

                stack.append((node.level, item))

            self._tree.expandAll()
        finally:
            self._tree.setUpdatesEnabled(True)

    def _on_item_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        value = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )
        try:
            line_number = int(value)
        except (TypeError, ValueError):
            return
        if line_number > 0:
            self.line_activated.emit(line_number)
