"""Serialize structured LaTeX Preview diagnostics for clipboard/reporting workflows."""

import yaml

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_node import (
    LatexDiagnosticNode,
)


class LatexDiagnosticSerializer:
    """Render one diagnostic as readable plain text or stable YAML."""

    def to_text(self, diagnostic: LatexDiagnostic) -> str:
        lines = [
            "LaTeX diagnostics",
            f"Summary: {diagnostic.summary}",
            "",
            "Raw compiler output:",
            diagnostic.raw_message or "(empty)",
            "",
            "Trace:",
        ]
        self._append_text_node(lines, diagnostic.root, depth=0)
        return "\n".join(lines).rstrip() + "\n"

    def to_yaml(self, diagnostic: LatexDiagnostic) -> str:
        payload = {
            "summary": diagnostic.summary,
            "raw_message": diagnostic.raw_message,
            "tree": self._node_dict(diagnostic.root),
        }
        return yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    def _append_text_node(
        self,
        lines: list[str],
        node: LatexDiagnosticNode,
        depth: int,
    ) -> None:
        indent = "  " * max(int(depth), 0)
        lines.append(f"{indent}- [{node.kind}] {node.title}")
        if node.detail:
            lines.append(f"{indent}  detail: {node.detail}")
        if node.source_path is not None:
            lines.append(
                f"{indent}  source: {node.source_path}:{node.line}:{node.column}"
            )
        if node.target_path is not None:
            lines.append(f"{indent}  target: {node.target_path}")
        for child in node.children:
            self._append_text_node(lines, child, depth + 1)

    def _node_dict(self, node: LatexDiagnosticNode) -> dict[str, object]:
        result: dict[str, object] = {
            "kind": node.kind,
            "title": node.title,
        }
        if node.detail:
            result["detail"] = node.detail
        if node.source_path is not None:
            result["source"] = {
                "path": str(node.source_path),
                "line": int(node.line),
                "column": int(node.column),
            }
        if node.target_path is not None:
            result["target_path"] = str(node.target_path)
        if node.children:
            result["children"] = [
                self._node_dict(child)
                for child in node.children
            ]
        return result
