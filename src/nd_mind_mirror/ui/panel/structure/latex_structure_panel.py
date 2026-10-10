"""Render navigable LaTeX/YAML structure and semantic LaTeX drag/drop editing."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QMenu,
    QSizePolicy,
    QTreeWidgetItem,
)

from nd_mind_mirror.core.latex.structure.latex_structure_level_planner import (
    LatexStructureLevelPlanner,
)
from nd_mind_mirror.core.latex.structure.latex_structure_title_matcher import (
    LatexStructureTitleMatcher,
)
from nd_mind_mirror.core.latex.structure.latex_structure_heading_catalog import (
    LatexStructureHeadingCatalog,
)
from nd_mind_mirror.core.latex.structure.latex_structure_move_planner import (
    LatexStructureMovePlanner,
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
from nd_mind_mirror.ui.panel.structure.latex_structure_tree import (
    LatexStructureTree,
)


class LatexStructurePanel(Panel):
    """Show Structure and request canonical source rewrites for LaTeX drops."""

    line_activated = Signal(int)
    source_rewrite_requested = Signal(str, str, int)

    _LARGE_DOCUMENT_THRESHOLD_CHARS = 120_000
    _LARGE_DOCUMENT_DEBOUNCE_MS = 650
    _LINE_ROLE = Qt.ItemDataRole.UserRole
    _SOURCE_POSITION_ROLE = Qt.ItemDataRole.UserRole + 1
    _SOURCE_END_ROLE = Qt.ItemDataRole.UserRole + 2
    _KIND_ROLE = Qt.ItemDataRole.UserRole + 3
    _LEVEL_ROLE = Qt.ItemDataRole.UserRole + 4
    _GENERATION_ROLE = Qt.ItemDataRole.UserRole + 5
    _TITLE_ROLE = Qt.ItemDataRole.UserRole + 6
    _LATEX_STRUCTURE_TOKENS = (
        "\\part",
        "\\chapter",
        "\\section",
        "\\subsection",
        "\\subsubsection",
        "\\paragraph",
        "\\subparagraph",
        "\\DeepSection",
        "\\ndsection",
        "\\subsubsub",
        "\\includegraphics",
        "\\caption",
        "\\begin{figure",
        "\\end{figure",
        "\\begin{table",
        "\\end{table",
        "\\begin{longtable",
        "\\end{longtable",
        "\\begin{tabular",
        "\\end{tabular",
    )

    def __init__(self, parent=None) -> None:
        super().__init__("Structure", parent)

        self._latex_parser = LatexStructureParser()
        self._move_planner = LatexStructureMovePlanner()
        self._level_planner = LatexStructureLevelPlanner()
        self._yaml_parser = YamlStructureParser()
        self._path: Path | None = None
        self._source = ""
        self._structure: list = []
        self._indent_width = 10
        self._current_line = 1
        self._structure_signature: tuple[tuple[int, str], ...] | None = None
        self._highlight_brush = QBrush(QColor("#fff6bf"))
        self._clear_brush = QBrush()
        self._parse_generation = 0
        self._applied_generation = -1
        self._latex_worker: LatexStructureParseWorker | None = None
        self._pending_async_rebuild = False
        self._expanded_before_filter: dict[int, bool] | None = None

        self.setMinimumWidth(90)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel("Structure", self)
        self._filter_input = QLineEdit(self)
        self._filter_input.setObjectName("structureSearchFilter")
        self._filter_input.setPlaceholderText("Search heading titles (typos OK)…")
        self._filter_input.setAccessibleName("Filter Structure headings")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(110)
        self._filter_timer.timeout.connect(self._apply_title_filter)
        self._filter_input.textChanged.connect(self._schedule_title_filter)
        self._filter_input.returnPressed.connect(self._activate_first_filter_match)
        self._tree = LatexStructureTree(self)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(self._indent_width)
        self._tree.setAnimated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_structure_context_menu)
        self._tree.structure_drop_requested.connect(self._on_structure_drop_requested)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(260)
        self._refresh_timer.timeout.connect(self._rebuild)

        self.panel_layout.addWidget(self._label)
        self.panel_layout.addWidget(self._filter_input)
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
        previous_path = self._path
        previous_source = self._source
        path_changed = file_path != previous_path

        self._path = file_path
        self._source = str(source)

        if file_path.suffix.lower() not in {".tex", ".yaml", ".yml"}:
            self.clear()
            return

        self._tree.setDragEnabled(file_path.suffix.lower() == ".tex")
        self._tree.setAcceptDrops(file_path.suffix.lower() == ".tex")
        self._tree.viewport().setAcceptDrops(file_path.suffix.lower() == ".tex")
        self._label.setText(f"Structure — {file_path.name}")

        if self._is_large_latex_document():
            if (
                not immediate
                and not path_changed
                and previous_source
                and not self._structure_change_requires_rescan(
                    previous_source,
                    self._source,
                )
            ):
                return

            self._parse_generation += 1
            self._structure_signature = None
            self._begin_structure_refresh(clear_tree=path_changed)
            self._refresh_timer.stop()
            self._refresh_timer.setInterval(
                0 if immediate or path_changed else self._LARGE_DOCUMENT_DEBOUNCE_MS
            )
            self._refresh_timer.start()
            return

        signature = self._signature_for(file_path, self._source)
        structure_changed = signature != self._structure_signature
        self._structure_signature = signature
        if not (immediate or path_changed or structure_changed):
            return

        self._parse_generation += 1
        self._refresh_timer.setInterval(260)
        if immediate or path_changed:
            self._refresh_timer.stop()
            self._rebuild()
        else:
            self._refresh_timer.start()

    def clear(self) -> None:
        self._refresh_timer.stop()
        self._parse_generation += 1
        self._applied_generation = -1
        self._pending_async_rebuild = False
        self._path = None
        self._source = ""
        self._structure = []
        self._structure_signature = None
        self._label.setText("Structure")
        self._tree.clear()
        self._expanded_before_filter = None
        self._filter_timer.stop()
        self._filter_input.clear()
        self._tree.setEnabled(True)

    def _begin_structure_refresh(self, *, clear_tree: bool) -> None:
        """Mark the visible tree stale while keeping existing rows navigable."""
        self._applied_generation = -1
        if clear_tree:
            self._structure = []
            self._tree.clear()

    @classmethod
    def _signature_for(
        cls,
        file_path: Path,
        source: str,
    ) -> tuple[tuple[int, str], ...]:
        """Return a cheap structural signature without rebuilding the tree."""
        suffix = file_path.suffix.lower()
        if suffix == ".tex":
            return tuple(
                (line_number, line.strip())
                for line_number, line in enumerate(source.splitlines(), start=1)
                if any(token in line for token in cls._LATEX_STRUCTURE_TOKENS)
            )
        if suffix in {".yaml", ".yml"}:
            return tuple(
                (line_number, line.rstrip())
                for line_number, line in enumerate(source.splitlines(), start=1)
                if (
                    line.strip()
                    and not line.lstrip().startswith("#")
                    and ":" in line
                )
            )
        return ()

    @classmethod
    def _structure_change_requires_rescan(
        cls,
        old: str,
        new: str,
    ) -> bool:
        """Return whether an edit can alter line mapping or Structure nodes."""
        if old == new:
            return False

        limit = min(len(old), len(new))
        prefix = 0
        chunk = 4096
        while (
            prefix + chunk <= limit
            and old[prefix:prefix + chunk] == new[prefix:prefix + chunk]
        ):
            prefix += chunk
        while prefix < limit and old[prefix] == new[prefix]:
            prefix += 1

        suffix_limit = min(len(old) - prefix, len(new) - prefix)
        suffix = 0
        while (
            suffix + chunk <= suffix_limit
            and old[len(old) - suffix - chunk:len(old) - suffix]
            == new[len(new) - suffix - chunk:len(new) - suffix]
        ):
            suffix += chunk
        while (
            suffix < suffix_limit
            and old[len(old) - suffix - 1] == new[len(new) - suffix - 1]
        ):
            suffix += 1

        old_end = len(old) - suffix
        new_end = len(new) - suffix
        old_changed = old[prefix:old_end]
        new_changed = new[prefix:new_end]
        if "\n" in old_changed or "\n" in new_changed:
            return True
        if "\\" in old_changed or "\\" in new_changed:
            return True

        def line_context(text: str, start: int, end: int) -> str:
            left = text.rfind("\n", 0, start) + 1
            right = text.find("\n", end)
            if right < 0:
                right = len(text)
            return text[left:right]

        context = (
            line_context(old, prefix, old_end)
            + "\n"
            + line_context(new, prefix, new_end)
        )
        return any(token in context for token in cls._LATEX_STRUCTURE_TOKENS)

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
        if generation != self._parse_generation or not isinstance(structure, list):
            return
        self._apply_structure(structure, generation=generation)

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

    def _apply_structure(
        self,
        structure: list,
        *,
        generation: int | None = None,
    ) -> None:
        """Replace the tree only from one complete current source snapshot."""
        applied_generation = (
            self._parse_generation if generation is None else int(generation)
        )
        if applied_generation != self._parse_generation:
            return
        self._structure = list(structure)
        self._applied_generation = applied_generation
        self._tree.setUpdatesEnabled(False)
        try:
            self._tree.clear()
            stack: list[tuple[int, QTreeWidgetItem]] = []
            for node in structure:
                while stack and stack[-1][0] >= node.level:
                    stack.pop()

                item = QTreeWidgetItem([f"{node.kind} — {node.title}"])
                item.setData(0, self._LINE_ROLE, node.line_number)
                item.setData(
                    0,
                    self._SOURCE_POSITION_ROLE,
                    int(getattr(node, "source_position", -1)),
                )
                item.setData(
                    0,
                    self._SOURCE_END_ROLE,
                    int(getattr(node, "source_end", -1)),
                )
                item.setData(0, self._KIND_ROLE, str(node.kind))
                item.setData(0, self._LEVEL_ROLE, int(node.level))
                item.setData(0, self._GENERATION_ROLE, applied_generation)
                item.setData(0, self._TITLE_ROLE, str(node.title))
                item.setToolTip(0, f"Line {node.line_number}: {node.kind}")

                if stack:
                    stack[-1][1].addChild(item)
                else:
                    self._tree.addTopLevelItem(item)
                stack.append((node.level, item))

            self._tree.expandAll()
            self._apply_title_filter()
            self._apply_current_line_highlight()
        finally:
            self._tree.setUpdatesEnabled(True)
            self._tree.viewport().update()

    def _schedule_title_filter(self, query: str) -> None:
        """Apply a cheap view-only filter after short typing bursts."""
        if not query.strip():
            self._filter_timer.stop()
            self._apply_title_filter()
        else:
            if self._expanded_before_filter is None:
                self._expanded_before_filter = {
                    int(item.data(0, self._SOURCE_POSITION_ROLE)): item.isExpanded()
                    for item in self._all_items_in_source_order()
                }
            self._filter_timer.start()

    def _apply_title_filter(self) -> None:
        """Retain matched headings plus ancestors; never rewrite the source."""
        query = self._filter_input.text().strip()
        latex = bool(self._path is not None and self._path.suffix.lower() == ".tex")
        self._tree.setUpdatesEnabled(False)
        try:
            def filter_branch(item: QTreeWidgetItem) -> bool:
                child_visible = False
                for index in range(item.childCount()):
                    if filter_branch(item.child(index)):
                        child_visible = True
                kind = str(item.data(0, self._KIND_ROLE) or "")
                allowed = not latex or LatexStructureHeadingCatalog.is_heading(kind)
                matches = allowed and LatexStructureTitleMatcher.matches(
                    str(item.data(0, self._TITLE_ROLE) or ""), query,
                )
                visible = not query or matches or child_visible
                item.setHidden(not visible)
                if query and visible:
                    item.setExpanded(True)
                return visible

            for index in range(self._tree.topLevelItemCount()):
                filter_branch(self._tree.topLevelItem(index))

            if not query and self._expanded_before_filter is not None:
                for item in self._all_items_in_source_order():
                    key = int(item.data(0, self._SOURCE_POSITION_ROLE))
                    if key in self._expanded_before_filter:
                        item.setExpanded(self._expanded_before_filter[key])
                self._expanded_before_filter = None
        finally:
            self._tree.setUpdatesEnabled(True)
            self._tree.viewport().update()

    def _activate_first_filter_match(self) -> None:
        """Enter navigates to the first title match, not a context-only ancestor."""
        query = self._filter_input.text().strip()
        if not query:
            return
        self._filter_timer.stop()
        self._apply_title_filter()
        latex = self._path is not None and self._path.suffix.lower() == ".tex"
        for item in self._all_items_in_source_order():
            kind = str(item.data(0, self._KIND_ROLE) or "")
            if latex and not LatexStructureHeadingCatalog.is_heading(kind):
                continue
            if LatexStructureTitleMatcher.matches(
                str(item.data(0, self._TITLE_ROLE) or ""), query,
            ):
                self._tree.scrollToItem(item)
                line = self._activation_line_for_item(item)
                if line > 0:
                    self.line_activated.emit(line)
                return

    def _on_structure_drop_requested(
        self,
        source_position: int,
        target_position: int,
        placement: str,
    ) -> None:
        """Translate one tree drop into one canonical-source edit request."""
        if self._path is None or self._path.suffix.lower() != ".tex":
            return
        result = self._move_planner.move(
            self._source,
            self._structure,
            source_position,
            target_position,
            placement,
        )
        if result is None:
            return
        rewritten, line_number = result
        if rewritten == self._source:
            return
        self.source_rewrite_requested.emit(
            self._source,
            rewritten,
            max(int(line_number), 1),
        )

    def _show_structure_context_menu(self, point) -> None:
        """Offer one-step heading promotion/demotion for complete nested subtrees."""
        item = self._tree.itemAt(point)
        if (
            item is None or self._path is None or self._path.suffix.lower() != ".tex"
            or self._applied_generation != self._parse_generation
            or item.data(0, self._GENERATION_ROLE) != self._applied_generation
        ):
            return
        position = int(item.data(0, self._SOURCE_POSITION_ROLE) or -1)
        node = next(
            (entry for entry in self._structure if entry.source_position == position),
            None,
        )
        if node is None or node.kind not in self._level_planner._HEADING_KINDS:
            return

        increase = self._level_planner.change(
            self._source, self._structure, position, -1,
        )
        decrease = self._level_planner.change(
            self._source, self._structure, position, 1,
        )
        menu = QMenu(self._tree)
        promote_action = menu.addAction("Increase Hierarchy")
        promote_action.setEnabled(increase is not None)
        demote_action = menu.addAction("Decrease Hierarchy")
        demote_action.setEnabled(decrease is not None)
        chosen = menu.exec(self._tree.viewport().mapToGlobal(point))
        result = increase if chosen == promote_action else decrease if chosen == demote_action else None
        if result is not None:
            updated_source, line_number = result
            if updated_source != self._source:
                self.source_rewrite_requested.emit(
                    self._source, updated_source, line_number,
                )

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
            key=lambda item: int(item.data(0, self._LINE_ROLE) or 0)
        )
        return items

    def _apply_current_line_highlight(self) -> None:
        """Clear every row and paint exactly one semantic Structure highlight."""
        items = self._all_items_in_source_order()
        target: QTreeWidgetItem | None = None
        self._tree.setUpdatesEnabled(False)
        try:
            self._tree.clearSelection()
            self._tree.setCurrentItem(None)
            for item in items:
                item.setBackground(0, self._clear_brush)
            for item in items:
                try:
                    item_line = int(item.data(0, self._LINE_ROLE))
                except (TypeError, ValueError):
                    continue
                if item_line > self._current_line:
                    break
                target = item
            if target is not None:
                target.setBackground(0, self._highlight_brush)
        finally:
            self._tree.setUpdatesEnabled(True)
            self._tree.viewport().update()

    def _on_item_clicked(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        del column
        line_number = self._activation_line_for_item(item)
        if line_number > 0:
            self.line_activated.emit(line_number)
        self._tree.clearSelection()

    def _activation_line_for_item(self, item: QTreeWidgetItem) -> int:
        """Resolve a clicked row against the current source instead of dropping stale clicks."""
        try:
            generation = int(item.data(0, self._GENERATION_ROLE))
            line_number = int(item.data(0, self._LINE_ROLE))
        except (TypeError, ValueError):
            return 0
        if (
            generation == self._parse_generation
            and generation == self._applied_generation
        ):
            return max(line_number, 0)

        try:
            source_position = int(item.data(0, self._SOURCE_POSITION_ROLE))
        except (TypeError, ValueError):
            source_position = -1
        kind = str(item.data(0, self._KIND_ROLE) or "")
        title = str(item.data(0, self._TITLE_ROLE) or "")
        if not title:
            text = item.text(0)
            title = text.split(" — ", 1)[1] if " — " in text else text

        structure = self._current_structure_snapshot()
        if not structure:
            return max(line_number, 0)

        candidates = [
            node
            for node in structure
            if str(node.kind) == kind and str(node.title) == title
        ]
        if not candidates:
            return max(line_number, 0)
        target = min(
            candidates,
            key=lambda node: abs(int(node.source_position) - source_position),
        )
        self._apply_structure(
            structure,
            generation=self._parse_generation,
        )
        return max(int(target.line_number), 0)

    def _current_structure_snapshot(self) -> list:
        """Parse the current source synchronously only for an explicit stale-row click."""
        if self._path is None:
            return []
        suffix = self._path.suffix.lower()
        if suffix == ".tex":
            return self._latex_parser.parse(self._source)
        if suffix in {".yaml", ".yml"}:
            return self._yaml_parser.parse(self._source)
        return []
