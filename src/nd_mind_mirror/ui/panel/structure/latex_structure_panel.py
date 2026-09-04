from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
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
from nd_mind_mirror.ui.panel.structure.latex_structure_parse_worker import (
    LatexStructureParseWorker,
)


class LatexStructurePanel(Panel):
    """Show the complete document structure without blocking large-file UI load."""

    line_activated = Signal(int)
    _LARGE_DOCUMENT_THRESHOLD_CHARS = 120_000
    _LARGE_DOCUMENT_DEBOUNCE_MS = 650

    def __init__(self, parent=None) -> None:
        super().__init__("Structure", parent)

        self._latex_parser = LatexStructureParser()
        self._yaml_parser = YamlStructureParser()
        self._path: Path | None = None
        self._source = ""
        self._indent_width = 10
        self._current_line = 1
        self._structure_signature: tuple[tuple[int, str], ...] | None = None
        self._highlight_brush = QBrush(QColor("#fff6bf"))
        self._clear_brush = QBrush()
        self._parse_generation = 0
        self._latex_worker: LatexStructureParseWorker | None = None
        self._pending_async_rebuild = False

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
        self._tree.itemClicked.connect(self._on_item_clicked)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(260)
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
        self._source = str(source)
        self._parse_generation += 1

        if file_path.suffix.lower() not in {".tex", ".yaml", ".yml"}:
            self.clear()
            return

        self._label.setText(f"Structure — {file_path.name}")

        if self._is_large_latex_document():
            # The full source is retained above. Parsing is merely moved off
            # the GUI thread so startup and tab switching can paint promptly.
            self._structure_signature = None
            self._refresh_timer.stop()
            self._refresh_timer.setInterval(
                0 if immediate or path_changed else self._LARGE_DOCUMENT_DEBOUNCE_MS
            )
            self._refresh_timer.start()
            return

        signature = self._signature_for(file_path, self._source)
        structure_changed = signature != self._structure_signature
        self._structure_signature = signature
        self._refresh_timer.setInterval(260)
        if immediate or path_changed:
            self._refresh_timer.stop()
            self._rebuild()
        elif structure_changed:
            self._refresh_timer.start()

    def clear(self) -> None:
        self._refresh_timer.stop()
        self._parse_generation += 1
        self._pending_async_rebuild = False
        self._path = None
        self._source = ""
        self._structure_signature = None
        self._label.setText("Structure")
        self._tree.clear()

    @staticmethod
    def _signature_for(
        file_path: Path,
        source: str,
    ) -> tuple[tuple[int, str], ...]:
        """Return a cheap structural signature without rebuilding the tree."""
        suffix = file_path.suffix.lower()
        if suffix == ".tex":
            tokens = (
                "\\part",
                "\\chapter",
                "\\section",
                "\\subsection",
                "\\subsubsection",
                "\\paragraph",
                "\\subparagraph",
                "\\includegraphics",
                "\\caption",
                "\\begin{figure",
                "\\end{figure",
            )
            return tuple(
                (line_number, line.strip())
                for line_number, line in enumerate(
                    source.splitlines(),
                    start=1,
                )
                if any(token in line for token in tokens)
            )
        if suffix in {".yaml", ".yml"}:
            return tuple(
                (line_number, line.rstrip())
                for line_number, line in enumerate(
                    source.splitlines(),
                    start=1,
                )
                if (
                    line.strip()
                    and not line.lstrip().startswith("#")
                    and ":" in line
                )
            )
        return ()

    def _is_large_latex_document(self) -> bool:
        return bool(
            self._path is not None
            and self._path.suffix.lower() == ".tex"
            and len(self._source) >= self._LARGE_DOCUMENT_THRESHOLD_CHARS
        )

    def _rebuild(self) -> None:
        if (
            self._path is None
            or self._path.suffix.lower() not in {".tex", ".yaml", ".yml"}
        ):
            self.clear()
            return

        if self._is_large_latex_document():
            self._start_async_latex_rebuild()
            return

        suffix = self._path.suffix.lower()
        structure = (
            self._latex_parser.parse(self._source)
            if suffix == ".tex"
            else self._yaml_parser.parse(self._source)
        )
        self._apply_structure(structure)

    def _start_async_latex_rebuild(self) -> None:
        worker = self._latex_worker
        if worker is not None and worker.isRunning():
            self._pending_async_rebuild = True
            return

        generation = self._parse_generation
        worker = LatexStructureParseWorker(
            generation,
            self._source,
            self,
        )
        self._latex_worker = worker
        self._pending_async_rebuild = False
        worker.parsed.connect(self._on_async_structure_parsed)
        worker.failed.connect(self._on_async_structure_failed)
        worker.finished.connect(
            lambda item=worker: self._on_async_worker_finished(item)
        )
        worker.start()

    def _on_async_structure_parsed(
        self,
        generation: int,
        structure: object,
    ) -> None:
        if generation != self._parse_generation:
            return
        if not isinstance(structure, list):
            return
        self._apply_structure(structure)

    def _on_async_structure_failed(
        self,
        generation: int,
        message: str,
    ) -> None:
        if generation != self._parse_generation:
            return
        name = self._path.name if self._path is not None else "document"
        self._label.setText(f"Structure — {name} (parse failed: {message})")

    def _on_async_worker_finished(
        self,
        worker: LatexStructureParseWorker,
    ) -> None:
        if self._latex_worker is worker:
            self._latex_worker = None
        worker.deleteLater()

        if self._pending_async_rebuild and self._is_large_latex_document():
            self._pending_async_rebuild = False
            QTimer.singleShot(0, self._start_async_latex_rebuild)

    def _apply_structure(self, structure: list) -> None:
        """Replace the tree from a complete parsed structure on the GUI thread."""
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
            self._apply_current_line_highlight()
        finally:
            self._tree.setUpdatesEnabled(True)

    def set_current_line(self, line_number: int) -> None:
        """Highlight the deepest structure item containing the cursor line."""
        self._current_line = max(int(line_number), 1)
        self._apply_current_line_highlight()

    def _all_items_in_source_order(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem) -> None:
            items.append(item)
            for index in range(item.childCount()):
                walk(item.child(index))

        for index in range(self._tree.topLevelItemCount()):
            walk(self._tree.topLevelItem(index))
        items.sort(
            key=lambda item: int(
                item.data(0, Qt.ItemDataRole.UserRole) or 0
            )
        )
        return items

    def _apply_current_line_highlight(self) -> None:
        items = self._all_items_in_source_order()
        target: QTreeWidgetItem | None = None
        self._tree.clearSelection()
        self._tree.setCurrentItem(None)
        for item in items:
            try:
                item_line = int(
                    item.data(
                        0,
                        Qt.ItemDataRole.UserRole,
                    )
                )
            except (TypeError, ValueError):
                continue
            item.setSelected(False)
            item.setBackground(0, self._clear_brush)
            if item_line <= self._current_line:
                target = item
            else:
                break
        if target is not None:
            target.setBackground(0, self._highlight_brush)

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
