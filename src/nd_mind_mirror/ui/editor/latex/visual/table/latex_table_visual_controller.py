"""Native QTextTable projection and structural editing for LaTeX tabular."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextFormat, QTextTable, QTextTableFormat

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta

from .latex_table_model import LatexTableModel
from .latex_table_parser import LatexTableParser


class LatexTableVisualController:
    """Own editable QTextTables and round-trip them back to canonical LaTeX."""

    _MODEL_PROPERTY = int(QTextFormat.Property.UserProperty) + 2301

    def __init__(self, editor) -> None:
        self._editor = editor
        self._parser = LatexTableParser()

    def insert_if_supported(
        self,
        cursor: QTextCursor,
        raw: str,
        source_line: int,
    ) -> bool:
        model = self._parser.parse(raw, source_line=source_line)
        if model is None:
            return False

        table_format = QTextTableFormat()
        table_format.setBorder(1.0)
        table_format.setCellPadding(6.0)
        table_format.setCellSpacing(0.0)
        table_format.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._write_model(table_format, model)

        table = cursor.insertTable(
            max(len(model.rows), 1),
            max(model.column_count, 1),
            table_format,
        )
        for row_index, row in enumerate(model.rows):
            for column_index in range(model.column_count):
                value = row[column_index] if column_index < len(row) else ""
                cell = table.cellAt(row_index, column_index)
                cell_cursor = cell.firstCursorPosition()
                cell_cursor.block().setUserData(
                    _BlockMeta(
                        kind="table_cell",
                        source_line=max(source_line + row_index, 0),
                    )
                )
                self._editor._insert_inline_latex(cell_cursor, value)

        self._move_cursor_after_table(cursor, table)
        return True

    def table_at_cursor(self, cursor: QTextCursor) -> QTextTable | None:
        table = cursor.currentTable()
        if table is None or not self._owns(table):
            return None
        return table

    def table_for_block(self, block) -> QTextTable | None:
        if not block.isValid():
            return None
        return self.table_at_cursor(QTextCursor(block))

    def has_tables(self) -> bool:
        block = self._editor.document().firstBlock()
        while block.isValid():
            if self.table_for_block(block) is not None:
                return True
            block = block.next()
        return False

    def build_context_actions(self, menu, cursor: QTextCursor):
        table = self.table_at_cursor(cursor)
        if table is None:
            return []
        cell = table.cellAt(cursor)
        if not cell.isValid():
            return []
        row = cell.row()
        column = cell.column()
        menu.addSeparator()
        actions = [
            (menu.addAction("Add row above"), "row_above", row, column),
            (menu.addAction("Add row below"), "row_below", row, column),
            (menu.addAction("Add column left"), "column_left", row, column),
            (menu.addAction("Add column right"), "column_right", row, column),
        ]
        delete_row = menu.addAction("Delete row")
        delete_row.setEnabled(table.rows() > 1)
        actions.append((delete_row, "delete_row", row, column))
        delete_column = menu.addAction("Delete column")
        delete_column.setEnabled(table.columns() > 1)
        actions.append((delete_column, "delete_column", row, column))
        return actions

    def apply_context_action(self, chosen, actions, cursor: QTextCursor) -> bool:
        if chosen is None:
            return False
        for action, operation, row, column in actions:
            if chosen is not action:
                continue
            table = self.table_at_cursor(cursor)
            if table is None:
                return False
            model = self._model_for_table(table)
            if model is None:
                return False
            if operation == "row_above":
                table.insertRows(row, 1)
                model.insert_row(row)
            elif operation == "row_below":
                table.insertRows(row + 1, 1)
                model.insert_row(row + 1)
            elif operation == "column_left":
                table.insertColumns(column, 1)
                model.insert_column(column)
            elif operation == "column_right":
                table.insertColumns(column + 1, 1)
                model.insert_column(column + 1)
            elif operation == "delete_row" and table.rows() > 1:
                table.removeRows(row, 1)
                model.remove_row(row)
            elif operation == "delete_column" and table.columns() > 1:
                table.removeColumns(column, 1)
                model.remove_column(column)
            else:
                return False
            self._write_model(table.format(), model, table=table)
            self._refresh_cell_metadata(table, model.source_line)
            return True
        return False

    def serialize_table(self, table: QTextTable) -> str:
        model = self._model_for_table(table)
        if model is None:
            return ""
        rows: list[list[str]] = []
        for row in range(table.rows()):
            values: list[str] = []
            for column in range(table.columns()):
                values.append(self._serialize_cell(table, row, column))
            rows.append(values)
        model.rows = rows
        model.normalize()
        return model.serialize()

    def next_block_after(self, table: QTextTable):
        document = self._editor.document()
        position = min(
            table.lastPosition() + 1,
            max(document.characterCount() - 1, 0),
        )
        block = document.findBlock(position)
        while block.isValid():
            current = QTextCursor(block).currentTable()
            if current is not table:
                return block
            block = block.next()
        return block

    def _serialize_cell(self, table: QTextTable, row: int, column: int) -> str:
        cell = table.cellAt(row, column)
        first = cell.firstCursorPosition().block()
        last_position = cell.lastCursorPosition().position()
        parts: list[str] = []
        block = first
        while block.isValid() and block.position() <= last_position:
            text = self._editor._serialize_inline_block(block)
            if text or not parts:
                parts.append(text)
            block = block.next()
        return r" \newline ".join(parts).strip()

    def _model_for_table(self, table: QTextTable) -> LatexTableModel | None:
        raw = table.format().property(self._MODEL_PROPERTY)
        if not raw:
            return None
        try:
            payload = json.loads(str(raw))
            return LatexTableModel(
                before_column_spec=str(payload["before_column_spec"]),
                column_spec=str(payload["column_spec"]),
                suffix=str(payload["suffix"]),
                rows=[[""] * max(table.columns(), 1) for _ in range(max(table.rows(), 1))],
                row_prefixes=[str(item) for item in payload.get("row_prefixes", [])],
                trailing_directives=str(payload.get("trailing_directives", "")),
                source_line=max(int(payload.get("source_line", 0)), 0),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_model(
        self,
        table_format: QTextTableFormat,
        model: LatexTableModel,
        *,
        table: QTextTable | None = None,
    ) -> None:
        payload = {
            "before_column_spec": model.before_column_spec,
            "column_spec": model.column_spec,
            "suffix": model.suffix,
            "row_prefixes": list(model.row_prefixes),
            "trailing_directives": model.trailing_directives,
            "source_line": model.source_line,
        }
        table_format.setProperty(
            self._MODEL_PROPERTY,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )
        if table is not None:
            table.setFormat(table_format)

    def _owns(self, table: QTextTable) -> bool:
        return bool(table.format().property(self._MODEL_PROPERTY))

    def _refresh_cell_metadata(self, table: QTextTable, source_line: int) -> None:
        for row in range(table.rows()):
            for column in range(table.columns()):
                block = table.cellAt(row, column).firstCursorPosition().block()
                if block.isValid():
                    block.setUserData(
                        _BlockMeta(
                            kind="table_cell",
                            source_line=max(source_line + row, 0),
                        )
                    )

    def _move_cursor_after_table(self, cursor: QTextCursor, table: QTextTable) -> None:
        document = self._editor.document()
        position = min(
            table.lastPosition() + 1,
            max(document.characterCount() - 1, 0),
        )
        cursor.setPosition(position)
