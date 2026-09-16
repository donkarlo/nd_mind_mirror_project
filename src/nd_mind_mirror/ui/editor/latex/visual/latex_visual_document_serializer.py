"""Serialize a Visual QTextDocument, including native editable LaTeX tables."""

from __future__ import annotations

import re

from PySide6.QtGui import QTextListFormat

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta


class LatexVisualDocumentSerializer:
    """Mirror the canonical Visual serializer while adding QTextTable support."""

    def __init__(self, editor, table_controller) -> None:
        self._editor = editor
        self._tables = table_controller

    def serialize(self) -> str:
        body_lines: list[str] = []
        block = self._editor.document().firstBlock()
        list_stack: list[str] = []

        def close_lists(target_depth: int = 0) -> None:
            while len(list_stack) > target_depth:
                environment = list_stack.pop()
                body_lines.append(
                    "    " * len(list_stack) + f"\\end{{{environment}}}"
                )

        def open_list(environment: str) -> None:
            body_lines.append(
                "    " * len(list_stack) + f"\\begin{{{environment}}}"
            )
            list_stack.append(environment)

        while block.isValid():
            table = self._tables.table_for_block(block)
            if table is not None:
                close_lists(0)
                raw_table = self._tables.serialize_table(table)
                if raw_table:
                    body_lines.extend(raw_table.splitlines())
                block = self._tables.next_block_after(table)
                continue

            data = block.userData()
            meta = data if isinstance(data, _BlockMeta) else _BlockMeta()
            text_list = block.textList()

            if text_list is not None or meta.kind == "list_item":
                fmt = text_list.format() if text_list is not None else None
                inferred_kind = "itemize"
                if fmt is not None and fmt.style() in {
                    QTextListFormat.Style.ListDecimal,
                    QTextListFormat.Style.ListLowerAlpha,
                    QTextListFormat.Style.ListUpperAlpha,
                    QTextListFormat.Style.ListLowerRoman,
                    QTextListFormat.Style.ListUpperRoman,
                }:
                    inferred_kind = "enumerate"
                list_kind = (
                    meta.command
                    if meta.command in {"itemize", "enumerate"}
                    else inferred_kind
                )
                depth = meta.depth
                if depth <= 0 and fmt is not None:
                    depth = max(int(fmt.indent()), 1)
                depth = max(depth, 1)
                depth = min(depth, len(list_stack) + 1)

                if len(list_stack) >= depth and list_stack[depth - 1] != list_kind:
                    close_lists(depth - 1)
                close_lists(depth)
                while len(list_stack) < depth:
                    open_list(list_kind)

                if meta.raw:
                    for directive in meta.raw.splitlines():
                        if directive.strip():
                            body_lines.append(
                                "    " * len(list_stack) + directive.strip()
                            )
                body_lines.append(
                    "    " * len(list_stack)
                    + r"\item "
                    + self._editor._serialize_inline_block(block)
                )
                block = block.next()
                continue

            close_lists(0)
            if meta.kind == "heading" and meta.command:
                serialized_title = self._editor._serialize_inline_block(block)
                if meta.raw and serialized_title == meta.display:
                    body_lines.append(meta.raw)
                else:
                    labels = ""
                    if meta.raw:
                        labels = "".join(
                            re.findall(r"\\label\s*\{[^}]*\}", meta.raw)
                        )
                    body_lines.append(
                        f"\\{meta.command}{{{serialized_title}}}{labels}"
                    )
            elif meta.kind == "graphic":
                body_lines.append(meta.raw)
            elif meta.kind == "raw":
                body_lines.append(meta.raw)
            elif meta.kind == "blank":
                body_lines.append("")
            else:
                body_lines.append(self._editor._serialize_inline_block(block))
            block = block.next()

        close_lists(0)
        body = "\n".join(body_lines).strip("\n")
        if self._editor._prefix:
            prefix = self._editor._prefix.rstrip()
            suffix = self._editor._suffix.lstrip()
            if body:
                return f"{prefix}\n\n{body}\n\n{suffix}"
            return f"{prefix}\n{suffix}"
        return body
